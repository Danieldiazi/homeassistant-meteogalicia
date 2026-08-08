"""Tests for the MeteoGalicia weather entity helpers."""

from types import SimpleNamespace

import pytest

from custom_components.meteogalicia.weather import (
    MeteoGaliciaWeather,
    _condition_from_code,
    _forecast_days,
    _maximum_probability,
    _valid_value,
    _weather_unique_id,
)


def test_condition_codes_are_mapped_and_unavailable_is_ignored():
    assert _condition_from_code(101) == "sunny"
    assert _condition_from_code(111) == "rainy"
    assert _condition_from_code(113) == "lightning-rainy"
    assert _condition_from_code(-9999) is None
    assert _condition_from_code("invalid") is None


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


def _weather_without_init(observation_data=None, forecast_data=None):
    entity = object.__new__(MeteoGaliciaWeather)
    entity._observation_coordinator = SimpleNamespace(data=observation_data)
    entity.coordinator = SimpleNamespace(data=forecast_data)
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
