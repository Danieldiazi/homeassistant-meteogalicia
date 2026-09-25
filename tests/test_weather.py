"""Tests for the MeteoGalicia weather entity helpers."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from homeassistant.components.weather import WeatherEntityFeature

from custom_components.meteogalicia import weather as weather_module
from custom_components.meteogalicia.weather import (
    MeteoGaliciaWeather,
    _condition_from_code,
    _forecast_days,
    _forecast_hours,
    _maximum_probability,
    _valid_value,
    _weather_unique_id,
    _wind_bearing_from_code,
)


def test_condition_codes_are_mapped_and_unavailable_is_ignored():
    assert _condition_from_code(101) == "sunny"
    assert _condition_from_code(111) == "rainy"
    assert _condition_from_code(113) == "lightning-rainy"
    assert _condition_from_code(-9999) is None
    assert _condition_from_code("invalid") is None


def test_night_codes_use_clear_night_only_for_clear_sky():
    assert _condition_from_code(201) == "clear-night"
    assert _condition_from_code(203) == "partlycloudy"
    assert _condition_from_code(211) == "rainy"
    assert _condition_from_code("201") == "clear-night"


def test_forecast_helpers_handle_valid_and_missing_data():
    day = {
        "pchoiva": {"manha": 10, "tarde": 60, "noite": -9999},
    }
    payload = {"predConcello": {"listaPredDiaConcello": [day]}}

    assert _forecast_days(payload) == [day]
    assert _forecast_days({}) == []
    assert _maximum_probability(day) == 60
    assert _maximum_probability({"pchoiva": {"manha": -9999}}) is None
    assert _valid_value(-9999) is None
    assert _valid_value(18) == 18


def _weather_without_init(observation_data=None, forecast_data=None, hourly_data=None):
    entity = object.__new__(MeteoGaliciaWeather)
    entity._observation_coordinator = SimpleNamespace(data=observation_data)
    entity.coordinator = SimpleNamespace(data=forecast_data)
    entity._hourly_coordinator = SimpleNamespace(data=hourly_data)
    return entity


def test_native_temperature_uses_observed_value():
    entity = _weather_without_init(
        {"listaObservacionConcellos": [{"temperatura": "18.4"}]}
    )

    assert entity.native_temperature == pytest.approx(18.4)


def test_apparent_temperature_and_condition_use_observed_values():
    entity = _weather_without_init(
        {
            "listaObservacionConcellos": [
                {
                    "temperatura": 18.4,
                    "sensacionTermica": "17.8",
                    "icoEstadoCeo": 111,
                }
            ]
        },
        forecast_data={"predConcello": {"listaPredDiaConcello": [{"ceoDia": 101}]}},
    )

    assert entity.native_apparent_temperature == pytest.approx(17.8)
    assert entity.condition == "rainy"


def test_condition_uses_clear_night_for_observed_night_clear_sky():
    entity = _weather_without_init(
        {"listaObservacionConcellos": [{"icoEstadoCeo": 201}]}
    )

    assert entity.condition == "clear-night"


def test_weather_exposes_real_observation_freshness():
    entity = _weather_without_init()
    entity._observation_coordinator = SimpleNamespace(
        data=None,
        data_timestamp="2026-08-08T16:17:00+00:00",
        data_age_seconds=180.0,
        data_is_stale=False,
    )

    assert entity.extra_state_attributes == {
        "observation_timestamp": "2026-08-08T16:17:00+00:00",
        "observation_age_s": 180.0,
        "observation_stale": False,
    }


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"listaObservacionConcellos": []},
        {"listaObservacionConcellos": [{"temperatura": -9999}]},
        {"listaObservacionConcellos": [{"temperatura": "invalid"}]},
    ],
)
def test_native_temperature_handles_unavailable_observations(payload):
    assert _weather_without_init(payload).native_temperature is None


def test_current_condition_does_not_fall_back_to_forecast():
    entity = _weather_without_init(
        observation_data={},
        forecast_data={
            "predConcello": {
                "listaPredDiaConcello": [
                    {"ceo": {"manha": 101, "tarde": 111, "noite": 203}}
                ]
            }
        },
    )

    assert entity.condition is None


@pytest.mark.asyncio
async def test_daily_forecast_uses_forecast_payload():
    entity = _weather_without_init(
        forecast_data={
            "predConcello": {
                "listaPredDiaConcello": [
                    {
                        "dataPredicion": "2026-08-08",
                        "ceoDia": 103,
                        "tMax": 24,
                        "tMin": 15,
                        "pchoiva": {"manha": 10, "tarde": 30, "noite": 20},
                        "uvMax": 7,
                    }
                ]
            }
        }
    )

    assert await entity.async_forecast_daily() == [
        {
            "datetime": "2026-08-08",
            "condition": "partlycloudy",
            "native_temperature": 24,
            "native_templow": 15,
            "precipitation_probability": 30,
            "uv_index": 7,
        }
    ]


@pytest.mark.asyncio
async def test_daily_forecast_handles_empty_response():
    assert await _weather_without_init(forecast_data={}).async_forecast_daily() is None


def test_weather_unique_id_is_new_and_stable():
    assert _weather_unique_id("15009") == "meteogalicia_weather_15009"
    assert _weather_unique_id("15009") != "meteogalicia_betanzos_temperature_15009"


def test_wind_codes_are_mapped_to_the_direction_they_blow_from():
    assert _wind_bearing_from_code(301) == 0.0  # light, N
    assert _wind_bearing_from_code(302) == 45.0  # light, NE
    assert _wind_bearing_from_code(308) == 315.0  # light, NW
    assert _wind_bearing_from_code(314) == 225.0  # moderate, SW
    assert _wind_bearing_from_code(321) == 180.0  # strong, S
    assert _wind_bearing_from_code(332) == 315.0  # very strong, NW
    assert _wind_bearing_from_code("303") == 90.0


@pytest.mark.parametrize("code", [299, 300, 333, 101, -9999, None, "invalid"])
def test_wind_codes_without_direction_are_ignored(code):
    assert _wind_bearing_from_code(code) is None


def _hourly_payload(*days):
    return {
        "predHoraria": {
            "idConcello": 15030,
            "nome": "A Coruña",
            "listaPredDiaHoraria": [
                {"dia": index, "listaPredHora": hours} for index, hours in enumerate(days)
            ],
        }
    }


def test_forecast_hours_join_every_day_and_skip_invalid_records():
    first = {"dataPredicion": "2026-09-26T23:00:00", "icoCeo": 203}
    second = {"dataPredicion": "2026-09-27T00:00:00", "icoCeo": 211}
    payload = _hourly_payload([first, "invalid"], [second])
    payload["predHoraria"]["listaPredDiaHoraria"].append("invalid")

    assert _forecast_hours(payload) == [first, second]
    assert _forecast_hours(None) == []
    assert _forecast_hours({"predHoraria": None}) == []
    assert _forecast_hours({"predHoraria": {"listaPredDiaHoraria": None}}) == []


@pytest.mark.asyncio
async def test_hourly_forecast_starts_at_the_current_hour(monkeypatch):
    monkeypatch.setattr(
        weather_module,
        "_now",
        lambda: datetime(2026, 9, 26, 1, 30, tzinfo=weather_module._FORECAST_TIME_ZONE),
    )
    entity = _weather_without_init(
        hourly_data=_hourly_payload(
            [
                {"dataPredicion": "2026-09-26T00:00:00", "icoCeo": 201, "icoVento": 302, "tMedia": 17},
                {"dataPredicion": "2026-09-26T01:00:00", "icoCeo": 203, "icoVento": 302, "tMedia": 15},
                {"dataPredicion": "2026-09-26T02:00:00", "icoCeo": 211, "icoVento": 299, "tMedia": -9999},
            ]
        )
    )

    assert await entity.async_forecast_hourly() == [
        {
            "datetime": "2026-09-26T01:00:00+02:00",
            "condition": "partlycloudy",
            "native_temperature": 15,
            "wind_bearing": 45.0,
        },
        {
            "datetime": "2026-09-26T02:00:00+02:00",
            "condition": "rainy",
            "native_temperature": None,
            "wind_bearing": None,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {}, _hourly_payload([])])
async def test_hourly_forecast_handles_missing_data(payload):
    assert await _weather_without_init(hourly_data=payload).async_forecast_hourly() is None


def test_weather_supports_daily_and_hourly_forecasts():
    features = _weather_without_init().supported_features

    assert features & WeatherEntityFeature.FORECAST_DAILY
    assert features & WeatherEntityFeature.FORECAST_HOURLY
