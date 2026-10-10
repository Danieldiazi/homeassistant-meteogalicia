"""Diagnostics stay useful when the remote service fails."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.helpers.entity import EntityCategory

from custom_components.meteogalicia import health


def test_health_sensors_are_optional_and_preserve_failure_diagnostics():
    coordinator = SimpleNamespace(
        _closed=False,
        last_update_success=False,
        last_success=None,
        data_age_seconds=None,
        consecutive_failures=3,
        last_failure_kind="timeout",
        last_failure_reason="Request timed out",
    )
    device = {"identifiers": {("meteogalicia", "1")}}
    sensors = health.create_health_sensors(coordinator, "resource_1", device)
    assert len({sensor.unique_id for sensor in sensors}) == 3
    assert all(sensor.available for sensor in sensors)
    assert all(
        sensor.entity_category == EntityCategory.DIAGNOSTIC for sensor in sensors
    )
    assert all(not sensor.entity_registry_enabled_default for sensor in sensors)
    assert all(sensor.device_info == device for sensor in sensors)
    assert [sensor.native_value for sensor in sensors] == [None, None, 3]
    assert sensors[2].extra_state_attributes["last_failure_kind"] == "timeout"
    coordinator.last_success = datetime(2026, 10, 10, tzinfo=UTC)
    coordinator.data_age_seconds = 120.0
    coordinator.consecutive_failures = 0
    assert sensors[0].native_value == coordinator.last_success
    assert sensors[1].native_value == 120.0
    coordinator._closed = True
    assert not any(sensor.available for sensor in sensors)


async def test_health_timer_is_local_and_registered_for_removal(monkeypatch):
    coordinator = SimpleNamespace(async_add_listener=Mock(return_value=Mock()))
    sensor = health.create_health_sensors(coordinator, "resource_1", {})[1]
    sensor.hass = SimpleNamespace(verify_event_loop_thread=lambda *_args: None)
    timer_stop = Mock()
    register = Mock(return_value=timer_stop)
    monkeypatch.setattr(health, "async_track_time_interval", register)
    removals = []
    monkeypatch.setattr(sensor, "async_on_remove", removals.append)
    await sensor.async_added_to_hass()
    assert register.call_args.args[2] == timedelta(minutes=1)
    assert timer_stop in removals
    write = Mock()
    monkeypatch.setattr(sensor, "async_write_ha_state", write)
    sensor._async_tick(None)
    write.assert_called_once()
    for remove in removals:
        remove()
    timer_stop.assert_called_once()
