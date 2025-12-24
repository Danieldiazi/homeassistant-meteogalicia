"""Diagnostics support for MeteoGalicia."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        }
    }
