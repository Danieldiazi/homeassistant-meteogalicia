"""Keep cached forecast dates and time slots correct between API downloads."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.meteogalicia import const, sensor, weather

ZONE = ZoneInfo("Europe/Madrid")


def _payload():
    return {"predConcello": {"listaPredDiaConcello": [
        {"dataPredicion": "2026-09-26T00:00:00", "tMax": 20,
         "pchoiva": {"manha": 10, "tarde": 20, "noite": 30}},
        {"dataPredicion": "2026-09-27T00:00:00", "tMax": 23,
         "pchoiva": {"manha": 40, "tarde": 50, "noite": 60}},
        {"dataPredicion": "2026-09-28T00:00:00", "tMax": 21,
         "pchoiva": {"manha": 70, "tarde": 80, "noite": 90}},
    ]}}


def _temperature(offset=0):
    instance = object.__new__(sensor.MeteoGaliciaForecastTemperatureByDaySensor)
    instance.coordinator = SimpleNamespace(data=_payload(), last_update_success=True)
    instance.id = "15030"
    instance.forecast_day = offset
    instance.forecast_field = "tMax"
    return instance


def test_today_and_tomorrow_roll_over_using_dates_not_list_positions(monkeypatch):
    current = datetime(2026, 9, 26, 23, 59, tzinfo=ZONE)
    monkeypatch.setattr(sensor.dt, "now", lambda *_args: current)
    today, tomorrow = _temperature(0), _temperature(1)
    today._update_from_data(today.coordinator.data)
    tomorrow._update_from_data(tomorrow.coordinator.data)
    assert (today.native_value, tomorrow.native_value) == (20, 23)

    current = datetime(2026, 9, 27, 0, 0, tzinfo=ZONE)
    today._update_from_data(today.coordinator.data)
    tomorrow._update_from_data(tomorrow.coordinator.data)
    assert (today.native_value, tomorrow.native_value) == (23, 21)
    assert today._attr[const.ATTR_FORECAST_DATE] == "2026-09-27T00:00:00"


def test_expired_or_missing_forecast_day_is_not_mislabeled_today(monkeypatch):
    monkeypatch.setattr(sensor.dt, "now", lambda *_args: datetime(2026, 9, 29, tzinfo=ZONE))
    today = _temperature()
    today._update_from_data(today.coordinator.data)
    assert today.native_value is None
    assert today._attr == {}


def test_forecast_uses_galician_date_even_when_home_assistant_uses_another_zone(monkeypatch):
    calls = []
    def now(zone=None):
        calls.append(zone)
        return datetime(2026, 9, 27, 0, 30, tzinfo=ZONE)
    monkeypatch.setattr(sensor.dt, "now", now)
    assert sensor._forecast_day(_payload(), 0)["tMax"] == 23
    assert calls == [ZONE]


def test_rain_recalculates_time_slot_between_downloads(monkeypatch):
    instance = object.__new__(sensor.MeteoGaliciaForecastRainByDaySensor)
    instance.coordinator = SimpleNamespace(data=_payload(), last_update_success=True)
    instance.id = "15030"
    instance.forecast_day = 0
    instance.max_value = False
    monkeypatch.setattr(sensor.dt, "now", lambda *_args: datetime(2026, 9, 26, 13, tzinfo=ZONE))
    instance._update_from_data(instance.coordinator.data)
    assert instance.native_value == 10
    monkeypatch.setattr(sensor.dt, "now", lambda *_args: datetime(2026, 9, 26, 14, tzinfo=ZONE))
    instance._update_from_data(instance.coordinator.data)
    assert instance.native_value == 20


def test_local_timer_does_not_request_data_or_change_last_connection():
    instance = _temperature()
    instance.coordinator.async_request_refresh = Mock()
    instance.coordinator.last_api_connected_at = "2026-09-26T20:00:00+00:00"
    instance._handle_coordinator_update = Mock()
    instance._refresh_forecast_time(None)
    instance._handle_coordinator_update.assert_called_once_with()
    instance.coordinator.async_request_refresh.assert_not_called()
    assert instance.coordinator.last_api_connected_at == "2026-09-26T20:00:00+00:00"


@pytest.mark.asyncio
async def test_weather_filters_past_short_and_medium_term_days(monkeypatch):
    monkeypatch.setattr(weather, "_now", lambda: datetime(2026, 9, 27, tzinfo=ZONE))
    instance = object.__new__(weather.MeteoGaliciaWeather)
    instance.coordinator = SimpleNamespace(data=_payload())
    instance._medium_term_coordinator = SimpleNamespace(data={"predMPrazo": {
        "listaPredDiaMPrazo": [
            {"dataPredicion": "2026-09-25T00:00:00"},
            {"dataPredicion": "2026-09-29T00:00:00"},
        ]
    }})
    result = await instance.async_forecast_daily()
    assert [row["datetime"][:10] for row in result] == ["2026-09-27", "2026-09-28", "2026-09-29"]


def test_weather_local_timer_only_pushes_cached_forecasts():
    instance = object.__new__(weather.MeteoGaliciaWeather)
    instance._async_push_forecast = Mock()
    instance.coordinator = SimpleNamespace(async_request_refresh=Mock())
    instance._refresh_forecast_time(None)
    assert [call.args for call in instance._async_push_forecast.call_args_list] == [("daily",), ("hourly",)]
    instance.coordinator.async_request_refresh.assert_not_called()
