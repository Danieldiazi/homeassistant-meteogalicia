"""Integration-level setup tests running a real Home Assistant instance."""

from datetime import datetime, timezone

import pytest

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteogalicia import const
from custom_components.meteogalicia import coordinator as coordinator_module


@pytest.mark.asyncio
async def test_municipality_entry_creates_weather_with_observed_freshness(
    hass, enable_custom_integrations, monkeypatch
):
    forecast = {
        "predConcello": {
            "nome": "Betanzos",
            "listaPredDiaConcello": [
                {
                    "dataPredicion": "2026-08-08T00:00:00",
                    "ceoDia": 101,
                    "tMax": 28,
                    "tMin": 17,
                    "pchoiva": {"manha": 5, "tarde": 10, "noite": 20},
                    "uvMax": 6,
                }
            ],
        }
    }
    observation = {
        "listaObservacionConcellos": [
            {
                "nomeConcello": "Betanzos",
                "dataLocal": "2026-08-08T18:17:00",
                "dataUTC": "2026-08-08T16:17:00",
                "temperatura": 28.0,
                "sensacionTermica": 28.5,
                "icoEstadoCeo": 101,
            }
        ]
    }
    monkeypatch.setattr(
        coordinator_module,
        "_get_forecast_data_from_api",
        lambda _resource_id, _session: forecast,
    )
    monkeypatch.setattr(
        coordinator_module,
        "_get_observation_data_from_api",
        lambda _resource_id, _session: observation,
    )
    monkeypatch.setattr(
        coordinator_module,
        "_utcnow",
        lambda: datetime(2026, 8, 8, 16, 20, tzinfo=timezone.utc),
    )
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        title="MeteoGalicia Betanzos",
        unique_id="concello_15009",
        data={const.CONF_ID_CONCELLO: "15009"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    weather_entries = [
        item
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.domain == "weather"
    ]
    assert len(weather_entries) == 1
    state = hass.states.get(weather_entries[0].entity_id)
    assert state is not None
    assert state.state == "sunny"
    assert state.attributes["temperature"] == 28.0
    assert state.attributes["apparent_temperature"] == 28.5
    assert state.attributes["observation_timestamp"] == ("2026-08-08T16:17:00+00:00")
    assert state.attributes["observation_stale"] is False

    observed_temperature = next(
        item
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.unique_id == "meteogalicia_betanzos_temperature_15009"
    )
    sensor_state = hass.states.get(observed_temperature.entity_id)
    assert sensor_state is not None
    assert sensor_state.attributes["data_timestamp"] == ("2026-08-08T16:17:00+00:00")
    assert sensor_state.attributes["data_stale"] is False

    assert await hass.config_entries.async_unload(entry.entry_id)
