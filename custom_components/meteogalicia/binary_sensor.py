"""Binary sensors for MeteoGalicia municipal weather warnings."""

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import MeteoGaliciaWarningsCoordinator, async_get_entry_coordinator
from .intervals import get_scan_interval, merge_entry_data

_WARNING_TIME_ZONE = ZoneInfo("Europe/Madrid")


def _merged_entry_data(entry):
    return merge_entry_data(entry)


def _parse_warning_time(value):
    """Parse MeteoGalicia warning timestamps expressed in Galicia local time."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_WARNING_TIME_ZONE)
    return parsed.astimezone(_WARNING_TIME_ZONE)


def _active_warning_items(data, now=None):
    """Return warnings whose validity interval contains the current local time."""
    current = now or datetime.now(_WARNING_TIME_ZONE)
    active = []
    for item in _warning_items(data):
        start = _parse_warning_time(item.get("dataIni"))
        end = _parse_warning_time(item.get("dataFin"))
        if start is None or end is None:
            continue
        if start <= current < end:
            active.append(item)
    return active


def _upcoming_warning_items(data, now=None):
    """Return warnings that start in the future."""
    current = now or datetime.now(_WARNING_TIME_ZONE)
    upcoming = []
    for item in _warning_items(data):
        start = _parse_warning_time(item.get("dataIni"))
        if start is not None and start > current:
            upcoming.append(item)
    return upcoming


def _warning_items(data):
    """Collect detailed warnings from every returned forecast day."""
    if not isinstance(data, dict):
        return []
    days = data.get("listaDiaConcellos")
    if not isinstance(days, list):
        return []
    warnings = []
    for day in days:
        if not isinstance(day, dict):
            continue
        items = day.get("listaAvisosConcellos")
        if isinstance(items, list):
            warnings.extend(item for item in items if isinstance(item, dict))
    return warnings


async def async_setup_entry(hass, entry, add_entities):
    """Set up the weather warning binary sensor when explicitly enabled."""
    data = _merged_entry_data(entry)
    id_concello = data.get(const.CONF_ID_CONCELLO)
    if not id_concello or not data.get(const.CONF_WARNINGS_ENABLED, False):
        return

    coordinator = await async_get_entry_coordinator(
        hass,
        entry.entry_id,
        MeteoGaliciaWarningsCoordinator,
        id_concello,
        get_scan_interval(data, const.CONF_OBSERVATION_INTERVAL),
    )
    name = entry.title.removeprefix("MeteoGalicia ").strip() or id_concello
    add_entities([MeteoGaliciaWeatherWarningBinarySensor(name, id_concello, coordinator)])


class MeteoGaliciaWeatherWarningBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Whether a MeteoGalicia municipal warning is active right now."""

    _attr_attribution = "Data provided by MeteoGalicia"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_translation_key = "weather_warning"

    def __init__(self, name, id_concello, coordinator):
        super().__init__(coordinator)
        self._name = name
        self._id_concello = id_concello
        self._attr_unique_id = f"meteogalicia_{id_concello}_weather_warning"
        self._unsub_transition = None
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, f"concello_{id_concello}")},
            name=f"{const.INTEGRATION_NAME} {name}",
            manufacturer=const.INTEGRATION_NAME,
        )

    async def async_added_to_hass(self) -> None:
        """Schedule local state changes at warning start/end boundaries."""
        await super().async_added_to_hass()
        self._schedule_next_transition()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the local transition timer when the entity is removed."""
        if self._unsub_transition is not None:
            self._unsub_transition()
            self._unsub_transition = None
        await super().async_will_remove_from_hass()

    def _schedule_next_transition(self) -> None:
        """Schedule the next local state refresh without polling MeteoGalicia."""
        if self._unsub_transition is not None:
            self._unsub_transition()
            self._unsub_transition = None
        now = datetime.now(_WARNING_TIME_ZONE)
        transitions = []
        for item in _warning_items(self.coordinator.data):
            for field in ("dataIni", "dataFin"):
                value = _parse_warning_time(item.get(field))
                if value is not None and value > now:
                    transitions.append(value)
        if transitions:
            self._unsub_transition = async_track_point_in_time(
                self.hass,
                self._async_warning_transition,
                min(transitions),
            )

    def _async_warning_transition(self, _now) -> None:
        """Refresh the local state at a warning boundary and schedule the next one."""
        self._unsub_transition = None
        self.async_write_ha_state()
        self._schedule_next_transition()

    def _handle_coordinator_update(self) -> None:
        """Reschedule boundaries whenever MeteoGalicia changes the warning data."""
        self._schedule_next_transition()
        super()._handle_coordinator_update()

    @property
    def is_on(self):
        """Return true only while at least one warning is currently active."""
        return bool(_active_warning_items(self.coordinator.data))

    @property
    def extra_state_attributes(self):
        """Expose all detailed warnings without discarding MeteoGalicia fields."""
        items = _warning_items(self.coordinator.data)
        active_items = _active_warning_items(self.coordinator.data)
        upcoming_items = _upcoming_warning_items(self.coordinator.data)
        levels = [
            item.get("idNivel")
            for item in items
            if isinstance(item.get("idNivel"), (int, float))
        ]
        active_levels = [
            item.get("idNivel")
            for item in active_items
            if isinstance(item.get("idNivel"), (int, float))
        ]
        return {
            "warning_count": len(items),
            "active_warning_count": len(active_items),
            "upcoming_warning_count": len(upcoming_items),
            "max_level": max(levels) if levels else 0,
            "active_max_level": max(active_levels) if active_levels else 0,
            "warning_types": sorted(
                {
                    str(item.get("tipoalerta_es") or item.get("tipoalerta_gl"))
                    for item in items
                    if item.get("tipoalerta_es") or item.get("tipoalerta_gl")
                }
            ),
            "active_warning_types": sorted(
                {
                    str(item.get("tipoalerta_es") or item.get("tipoalerta_gl"))
                    for item in active_items
                    if item.get("tipoalerta_es") or item.get("tipoalerta_gl")
                }
            ),
            "warnings": items,
            "active_warnings": active_items,
            "upcoming_warnings": upcoming_items,
        }
