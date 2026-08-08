"""Diagnostics support for MeteoGalicia."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import const


def _serializable(value):
    """Return a diagnostics-safe scalar value."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _coordinator_diagnostics(coordinator) -> dict:
    """Return useful coordinator health without exposing API payloads."""
    interval = getattr(coordinator, "update_interval", None)
    return {
        "class": coordinator.__class__.__name__,
        "name": getattr(coordinator, "name", None),
        "resource_id": getattr(coordinator, "id", None),
        "last_update_success": bool(getattr(coordinator, "last_update_success", False)),
        "last_successful_api_connection": getattr(
            coordinator, "last_api_connected_at", None
        ),
        "last_api_latency_ms": getattr(coordinator, "last_api_latency_ms", None),
        "data_timestamp": getattr(coordinator, "data_timestamp", None),
        "data_age_seconds": getattr(coordinator, "data_age_seconds", None),
        "data_stale": getattr(coordinator, "data_is_stale", None),
        "scan_interval_seconds": (
            interval.total_seconds() if interval is not None else None
        ),
        "last_error": _serializable(getattr(coordinator, "last_exception", None)),
        "data_available": getattr(coordinator, "data", None) is not None,
    }


def _entry_type(entry: ConfigEntry) -> str:
    """Return the configured MeteoGalicia resource type."""
    data = {**entry.data, **entry.options}
    if data.get(const.CONF_ID_CONCELLO):
        return "municipality"
    if data.get(const.CONF_ID_ESTACION):
        return "station"
    return "unknown"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    entry_data = hass.data.get(const.DOMAIN, {}).get(entry.entry_id, {})
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    return {
        "entry": {
            "entry_id": entry.entry_id,
            "type": _entry_type(entry),
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinators": [
            _coordinator_diagnostics(coordinator)
            for coordinator in entry_data.get("coordinators", [])
        ],
        "entities": [
            {
                "entity_id": entity.entity_id,
                "unique_id": entity.unique_id,
                "platform": entity.platform,
                "disabled_by": _serializable(entity.disabled_by),
            }
            for entity in entities
        ],
    }
