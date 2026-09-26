"""Polling defaults, legacy compatibility and user-controlled overrides."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
import voluptuous as vol
from probatio import to_field_list

from custom_components.meteogalicia import config_flow, const, coordinator, sensor
from custom_components.meteogalicia.intervals import get_scan_interval, merge_entry_data


def _suggested_values(form):
    return {
        key.schema: key.description["suggested_value"]
        for key in form["data_schema"].schema
        if isinstance(key.description, dict) and "suggested_value" in key.description
    }


def test_interval_form_schema_can_be_serialized_for_the_frontend():
    schema = vol.Schema({vol.Optional("interval"): config_flow._INTERVAL_VALIDATOR})
    fields = to_field_list(schema, custom_serializer=config_flow.cv.custom_serializer)
    assert fields[0]["name"] == "interval"
    assert fields[0]["type"] == "integer"


@pytest.mark.parametrize("key,expected", const.DEFAULT_INTERVALS.items())
def test_missing_interval_uses_service_default(key, expected):
    assert get_scan_interval({}, key) == expected
    assert get_scan_interval({"scan_interval": None}, key) == expected


@pytest.mark.parametrize("key", const.DEFAULT_INTERVALS)
@pytest.mark.parametrize("legacy", [15, 120, 1700, 90000])
def test_explicit_legacy_interval_is_preserved_for_every_service(key, legacy):
    assert get_scan_interval({"scan_interval": legacy}, key) == legacy


def test_options_override_entry_data_without_resetting_other_services():
    entry = SimpleNamespace(
        data={"scan_interval": 120, const.CONF_ID_CONCELLO: "15030"},
        options={"scan_interval": 1700, const.CONF_FORECAST_INTERVAL: 7200},
    )
    data = merge_entry_data(entry)
    assert get_scan_interval(data, const.CONF_OBSERVATION_INTERVAL) == 1700
    assert get_scan_interval(data, const.CONF_FORECAST_INTERVAL) == 7200
    assert entry.data["scan_interval"] == 120


@pytest.mark.parametrize("empty", [None, ""])
def test_clearing_a_service_restores_default_even_with_legacy_interval(empty):
    entry = SimpleNamespace(
        data={"scan_interval": 15, const.CONF_FORECAST_INTERVAL: 120},
        options={const.CONF_FORECAST_INTERVAL: empty},
    )
    data = merge_entry_data(entry)
    assert get_scan_interval(data, const.CONF_FORECAST_INTERVAL) == 21600
    assert get_scan_interval(data, const.CONF_OBSERVATION_INTERVAL) == 15


def test_clearing_a_legacy_option_still_clears_its_entry_value():
    data = merge_entry_data(SimpleNamespace(
        data={"scan_interval": 120}, options={"scan_interval": None}
    ))
    assert get_scan_interval(data, const.CONF_OBSERVATION_INTERVAL) == 600


def test_legacy_timedelta_is_supported():
    assert get_scan_interval(
        {"scan_interval": timedelta(seconds=1700)}, const.CONF_FORECAST_INTERVAL
    ) == 1700


@pytest.mark.asyncio
@pytest.mark.parametrize("cls,seconds", [
    (coordinator.MeteoGaliciaObservationCoordinator, 600),
    (coordinator.MeteoGaliciaStationLast10MinCoordinator, 600),
    (coordinator.MeteoGaliciaStationDailyCoordinator, 3600),
    (coordinator.MeteoGaliciaForecastCoordinator, 21600),
    (coordinator.MeteoGaliciaHourlyForecastCoordinator, 21600),
    (coordinator.MeteoGaliciaMediumTermForecastCoordinator, 21600),
])
async def test_coordinator_defaults_do_not_depend_on_home_assistant(hass, cls, seconds):
    instance = cls(hass, "15030", None)
    try:
        assert instance.update_interval == timedelta(seconds=seconds)
    finally:
        await instance.async_close()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [1, 15, 300, 90000])
async def test_options_allow_intervals_below_recommendation_and_above_one_day(hass, value):
    entry = SimpleNamespace(data={const.CONF_ID_CONCELLO: "15030"}, options={})
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    result = await flow.async_step_init({
        const.CONF_ID_CONCELLO: "15030",
        const.CONF_OBSERVATION_INTERVAL: value,
        const.CONF_FORECAST_INTERVAL: value,
    })
    assert result["type"] == "create_entry"
    assert result["data"][const.CONF_OBSERVATION_INTERVAL] == value
    assert result["data"][const.CONF_FORECAST_INTERVAL] == value


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -10, "invalid", 1.5, True])
async def test_options_reject_invalid_intervals(hass, value):
    entry = SimpleNamespace(data={const.CONF_ID_CONCELLO: "15030"}, options={})
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    result = await flow.async_step_init({
        const.CONF_ID_CONCELLO: "15030", const.CONF_FORECAST_INTERVAL: value,
    })
    assert result["type"] == "form"
    assert result["errors"] == {const.CONF_FORECAST_INTERVAL: "invalid_interval"}


@pytest.mark.asyncio
async def test_options_show_legacy_values_and_allow_reset(hass):
    entry = SimpleNamespace(
        data={const.CONF_ID_CONCELLO: "15030", "scan_interval": 1700}, options={}
    )
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    form = await flow.async_step_init()
    serialized = to_field_list(
        form["data_schema"], custom_serializer=config_flow.cv.custom_serializer
    )
    assert any(field["name"] == const.CONF_FORECAST_INTERVAL for field in serialized)
    defaults = _suggested_values(form)
    assert defaults[const.CONF_OBSERVATION_INTERVAL] == 1700
    assert defaults[const.CONF_FORECAST_INTERVAL] == 1700
    result = await flow.async_step_init({
        const.CONF_ID_CONCELLO: "15030", const.CONF_FORECAST_INTERVAL: None,
        const.CONF_OBSERVATION_INTERVAL: 1700,
    })
    entry.options = result["data"]
    assert get_scan_interval(merge_entry_data(entry), const.CONF_FORECAST_INTERVAL) == 21600
    assert get_scan_interval(merge_entry_data(entry), const.CONF_OBSERVATION_INTERVAL) == 1700


@pytest.mark.asyncio
async def test_station_options_offer_independent_defaults(hass):
    entry = SimpleNamespace(data={const.CONF_ID_ESTACION: "14000"}, options={})
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    form = await flow.async_step_init()
    values = _suggested_values(form)
    assert values[const.CONF_OBSERVATION_INTERVAL] == 600
    assert values[const.CONF_STATION_DAILY_INTERVAL] == 3600
    assert const.CONF_FORECAST_INTERVAL not in values


@pytest.mark.asyncio
async def test_clearing_a_field_in_the_frontend_resets_previous_options(hass):
    entry = SimpleNamespace(
        data={const.CONF_ID_CONCELLO: "15030", "scan_interval": 15},
        options={const.CONF_FORECAST_INTERVAL: 120},
    )
    flow = config_flow.MeteoGaliciaOptionsFlowHandler(entry)
    flow.hass = hass
    result = await flow.async_step_init({
        const.CONF_ID_CONCELLO: "15030", const.CONF_OBSERVATION_INTERVAL: 900,
        # Clearing forecast_interval removes the key from the frontend payload.
    })
    assert result["data"][const.CONF_FORECAST_INTERVAL] is None
    entry.options = result["data"]
    assert get_scan_interval(merge_entry_data(entry), const.CONF_FORECAST_INTERVAL) == 21600
    assert get_scan_interval(merge_entry_data(entry), const.CONF_OBSERVATION_INTERVAL) == 900


def test_yaml_without_interval_does_not_inject_home_assistant_default():
    validated = sensor.PLATFORM_SCHEMA({
        "platform": const.DOMAIN, const.CONF_ID_ESTACION: "14000",
    })
    imported = sensor._yaml_import_data(validated)
    assert "scan_interval" not in imported
    assert get_scan_interval(imported, const.CONF_STATION_DAILY_INTERVAL) == 3600


def test_yaml_explicit_interval_remains_unchanged_after_validation():
    validated = sensor.PLATFORM_SCHEMA({
        "platform": const.DOMAIN, const.CONF_ID_ESTACION: "14000", "scan_interval": 15,
    })
    imported = sensor._yaml_import_data(validated)
    assert imported["scan_interval"] == 15
