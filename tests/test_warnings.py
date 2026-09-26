"""Weather warnings using the daily response shape of the public service."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteogalicia import const
from custom_components.meteogalicia import coordinator as coordinator_module
from custom_components.meteogalicia import binary_sensor as binary_sensor_module
from custom_components.meteogalicia.binary_sensor import (
    MeteoGaliciaWeatherWarningBinarySensor,
    _active_warning_items,
    _upcoming_warning_items,
    _warning_items,
)
from custom_components.meteogalicia.sensor import (
    MeteoGaliciaWarningLevelSensor,
    _WARNING_LEVEL_NAMES,
)


def _fixture(name):
    return json.loads(
        (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")
    )


def _level_sensor(data, day=0):
    entity = object.__new__(MeteoGaliciaWarningLevelSensor)
    entity.coordinator = SimpleNamespace(data=data, last_update_success=True)
    entity.id = "15030"
    entity._day_index = day
    return entity


def test_warning_items_preserve_detailed_payload():
    warning = {
        "idNivel": 2,
        "tipoalerta_es": "Viento",
        "dataIni": "2026-09-27T06:00:00",
        "dataFin": "2026-09-27T18:00:00",
    }

    other = {"idNivel": 1, "tipoalerta_gl": "Choiva"}
    payload = {"listaDiaConcellos": [
        {"dia": 2, "listaAvisosConcellos": [other]},
        {"dia": 0, "listaAvisosConcellos": []},
        {"dia": 1, "listaAvisosConcellos": [warning]},
    ]}
    assert _warning_items(payload) == [other, warning]
    entity = object.__new__(MeteoGaliciaWeatherWarningBinarySensor)
    entity.coordinator = SimpleNamespace(data=payload)
    assert entity.is_on is False
    attrs = entity.extra_state_attributes
    assert attrs["warning_count"] == 2
    assert attrs["active_warning_count"] == 0
    assert attrs["max_level"] == 2
    assert attrs["active_max_level"] == 0
    assert attrs["warning_types"] == ["Choiva", "Viento"]
    assert attrs["warnings"] == [other, warning]


def test_active_and_upcoming_warnings_are_distinguished_by_time():
    now = datetime(2026, 9, 27, 10, 0, tzinfo=binary_sensor_module._WARNING_TIME_ZONE)
    active = {
        "idNivel": 2,
        "tipoalerta_es": "Viento",
        "dataIni": "2026-09-27T08:00:00",
        "dataFin": "2026-09-27T18:00:00",
    }
    upcoming = {
        "idNivel": 1,
        "tipoalerta_es": "Lluvia",
        "dataIni": "2026-09-28T06:00:00",
        "dataFin": "2026-09-28T12:00:00",
    }
    expired = {
        "idNivel": 1,
        "tipoalerta_es": "Niebla",
        "dataIni": "2026-09-27T00:00:00",
        "dataFin": "2026-09-27T07:00:00",
    }
    payload = {"listaDiaConcellos": [{"dia": 0, "listaAvisosConcellos": [active, upcoming, expired]}]}

    assert _active_warning_items(payload, now) == [active]
    assert _upcoming_warning_items(payload, now) == [upcoming]


def test_warning_end_boundary_is_not_active():
    warning = {
        "idNivel": 2,
        "dataIni": "2026-09-27T08:00:00",
        "dataFin": "2026-09-27T18:00:00",
    }
    payload = {"listaDiaConcellos": [{"dia": 0, "listaAvisosConcellos": [warning]}]}
    at_end = datetime(2026, 9, 27, 18, 0, tzinfo=binary_sensor_module._WARNING_TIME_ZONE)
    assert _active_warning_items(payload, at_end) == []


def test_warning_items_ignore_invalid_payload():
    assert _warning_items(None) == []
    assert _warning_items({}) == []
    assert _warning_items({"listaDiaConcellos": None}) == []
    assert _warning_items({"listaDiaConcellos": [None, {"dia": 0, "listaAvisosConcellos": None}]}) == []
    assert _warning_items({"listaDiaConcellos": [{"dia": 0, "listaAvisosConcellos": ["bad", {"idNivel": 1}]}]}) == [
        {"idNivel": 1}
    ]


def test_real_no_warning_response_is_off_and_all_levels_are_normal():
    entity = object.__new__(MeteoGaliciaWeatherWarningBinarySensor)
    entity.coordinator = SimpleNamespace(data=_fixture("warnings_all_days.json"))
    assert entity.is_on is False
    assert entity.extra_state_attributes["warning_count"] == 0

    for day in range(3):
        sensor = _level_sensor(_fixture("warning_levels_all_days.json"), day)
        assert sensor.native_value == "normal"
        assert sensor.extra_state_attributes["level"] == 0


def test_levels_follow_day_and_municipality_instead_of_list_order():
    payload = {"listaDiaConcellos": [
        {"dia": day, "listaNiveisMaximos": [
            {"idConcello": 15009, "nivelMax": 3},
            {"idConcello": 15030, "nivelMax": level},
        ]}
        for day, level in [(2, 1), (0, 0), (1, 2)]
    ]}
    assert [_level_sensor(payload, day).native_value for day in range(3)] == [
        "normal", "orange", "yellow"
    ]
    assert [_level_sensor(payload, day).extra_state_attributes["level"] for day in range(3)] == [0, 2, 1]


@pytest.mark.parametrize("payload", [
    None, {}, [], {"listaDiaConcellos": None},
    {"listaDiaConcellos": [None, {"dia": 0, "listaNiveisMaximos": None}]},
    {"listaDiaConcellos": [{"dia": 1, "listaNiveisMaximos": [{"idConcello": 15030, "nivelMax": 2}]}]},
    {"listaDiaConcellos": [{"dia": 0, "listaNiveisMaximos": [{"idConcello": 15009, "nivelMax": 2}]}]},
    {"listaDiaConcellos": [{"dia": 0, "listaNiveisMaximos": [None, {"idConcello": 15030, "nivelMax": None}]}]},
])
def test_missing_day_or_invalid_level_is_unknown_not_normal(payload):
    assert _level_sensor(payload).native_value is None


def test_warning_level_names_match_meteogalicia_scale():
    assert _WARNING_LEVEL_NAMES == {
        0: "normal",
        1: "yellow",
        2: "orange",
        3: "red",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
async def test_warning_entities_through_real_client_and_coordinators(
    hass, enable_custom_integrations, monkeypatch, active
):
    """Exercise HTTP parsing, client validation, both coordinators and HA states."""
    warnings = _fixture("warnings_all_days.json")
    levels = _fixture("warning_levels_all_days.json")
    if active:
        now = datetime.now(binary_sensor_module._WARNING_TIME_ZONE)
        warnings["listaDiaConcellos"][1]["listaAvisosConcellos"] = [
            {
                "idConcello": 15030,
                "idNivel": 2,
                "tipoalerta_es": "Viento",
                "dataIni": (now - timedelta(hours=1)).replace(microsecond=0).isoformat(),
                "dataFin": (now + timedelta(hours=1)).replace(microsecond=0).isoformat(),
            }
        ]
        levels["listaDiaConcellos"][1]["listaNiveisMaximos"][0]["nivelMax"] = 2
    levels["listaDiaConcellos"].reverse()
    response_state = {"failed": False}

    def http_get(_session, url, **kwargs):
        assert "idConcello=15030&dia=-1" in url
        payload = warnings if "jsonAvisosConcellos" in url else levels
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({} if response_state["failed"] else payload).encode()
        return response

    monkeypatch.setattr(requests.Session, "get", http_get)
    monkeypatch.setattr(coordinator_module, "_get_forecast_data_from_api", lambda *_: {
        "predConcello": {"nome": "A Coruña", "listaPredDiaConcello": []}
    })
    monkeypatch.setattr(coordinator_module, "_get_observation_data_from_api", lambda *_: {
        "listaObservacionConcellos": []
    })
    monkeypatch.setattr(coordinator_module, "_get_hourly_forecast_data_from_api", lambda *_: {
        "predHoraria": {"listaPredDiaHoraria": []}
    })
    monkeypatch.setattr(coordinator_module, "_get_medium_term_forecast_data_from_api", lambda *_: {
        "predMPrazo": {"listaPredDiaMPrazo": []}
    })
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        title="MeteoGalicia A Coruña",
        unique_id="concello_15030",
        data={const.CONF_ID_CONCELLO: "15030", const.CONF_WARNINGS_ENABLED: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    def state(domain, suffix):
        entity_id = registry.async_get_entity_id(domain, const.DOMAIN, f"meteogalicia_15030_{suffix}")
        assert entity_id is not None
        return hass.states.get(entity_id)

    def assert_valid_states():
        binary = state("binary_sensor", "weather_warning")
        assert binary.state == ("on" if active else "off")
        assert binary.attributes["warning_count"] == int(active)
        assert binary.attributes["active_warning_count"] == int(active)
        assert binary.attributes["upcoming_warning_count"] == 0
        for day, name in enumerate(("today", "tomorrow", "day_after_tomorrow")):
            sensor = state("sensor", f"warning_level_{name}")
            assert sensor.state == ("orange" if active and day == 1 else "normal")
            assert sensor.attributes["level"] == (2 if active and day == 1 else 0)

    assert_valid_states()
    warning_coordinators = [
        item for item in hass.data[const.DOMAIN][entry.entry_id]["coordinators"]
        if isinstance(item, (coordinator_module.MeteoGaliciaWarningsCoordinator,
                             coordinator_module.MeteoGaliciaMaxWarningLevelsCoordinator))
    ]
    assert len(warning_coordinators) == 2
    response_state["failed"] = True
    for coordinator in warning_coordinators:
        await coordinator.async_refresh()
    assert state("binary_sensor", "weather_warning").state == "unavailable"
    for name in ("today", "tomorrow", "day_after_tomorrow"):
        assert state("sensor", f"warning_level_{name}").state == "unavailable"

    response_state["failed"] = False
    for coordinator in warning_coordinators:
        await coordinator.async_refresh()
    assert_valid_states()
    assert await hass.config_entries.async_unload(entry.entry_id)
