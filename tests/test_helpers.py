import types
from datetime import datetime, timezone

from custom_components.meteogalicia import sensor
from pytest import approx


def test_get_coordinator_connected_at_from_iso_string():
    class Dummy:
        last_api_connected_at = "2024-01-01T12:00:00+00:00"

    assert sensor._get_coordinator_connected_at(Dummy()) == "2024-01-01T12:00:00+00:00"


def test_get_coordinator_connected_at_from_datetime():
    class Dummy:
        last_api_connected_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert sensor._get_coordinator_connected_at(Dummy()) == "2024-01-01T12:00:00+00:00"


def test_get_coordinator_connected_at_unknown():
    class Dummy:
        last_api_connected_at = None

    assert sensor._get_coordinator_connected_at(Dummy()) == sensor.STATE_UNKNOWN


def test_get_coordinator_api_latency_ms_ok():
    class Dummy:
        last_api_latency_ms = "123.4"

    assert sensor._get_coordinator_api_latency_ms(Dummy()) == approx(123.4)


def test_get_coordinator_api_latency_ms_unknown():
    class Dummy:
        last_api_latency_ms = None

    assert sensor._get_coordinator_api_latency_ms(Dummy()) == sensor.STATE_UNKNOWN


def test_get_state_forecast_rain_by_day_sensor_max():
    item = {"pchoiva": {"manha": 10, "tarde": 20, "noite": 5}}
    assert sensor.get_state_forecast_rain_by_day_sensor(True, item) == 20


def test_get_state_forecast_rain_by_day_sensor_slot():
    item = {"pchoiva": {"manha": 10, "tarde": 20, "noite": 5}}
    # For a fixed hour, simulate night slot
    original_now = sensor.dt.now
    sensor.dt.now = classmethod(lambda cls: datetime(2024, 1, 1, 23, 0))
    try:
        assert sensor.get_state_forecast_rain_by_day_sensor(False, item) == 5
    finally:
        sensor.dt.now = original_now


def test_get_state_forecast_rain_by_day_sensor_invalid():
    item = {"pchoiva": {"manha": -9999}}
    assert sensor.get_state_forecast_rain_by_day_sensor(True, item) is None
