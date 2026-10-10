"""The MeteoGalicia integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_RESET_ENTITIES, DOMAIN
from .util import safe_close_coordinators

PLATFORMS = ["binary_sensor", "sensor", "weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MeteoGalicia from a config entry."""
    if entry.data.get(CONF_RESET_ENTITIES):
        # The options flow has unloaded the old platforms before this setup.
        # Changing a resource must not leave its old sensors/devices registered.
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            entity_registry.async_remove(entity.entity_id)
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            if hasattr(device, "config_entry_id"):
                device_registry.async_remove_device(device.id)
            else:
                # Older Core versions allow several entries to share a device.
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )
        data = dict(entry.data)
        data.pop(CONF_RESET_ENTITIES)
        hass.config_entries.async_update_entry(entry, data=data)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinators": []}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data:
        await safe_close_coordinators(data.get("coordinators", []))
    return True
