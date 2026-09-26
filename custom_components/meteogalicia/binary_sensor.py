"""Binary sensors for MeteoGalicia municipal weather warnings."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import MeteoGaliciaWarningsCoordinator, async_get_entry_coordinator
from .intervals import get_scan_interval, merge_entry_data


def _merged_entry_data(entry):
    return merge_entry_data(entry)


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
    """Whether MeteoGalicia reports any municipal warning in the requested horizon."""

    _attr_attribution = "Data provided by MeteoGalicia"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_translation_key = "weather_warning"

    def __init__(self, name, id_concello, coordinator):
        super().__init__(coordinator)
        self._name = name
        self._id_concello = id_concello
        self._attr_unique_id = f"meteogalicia_{id_concello}_weather_warning"
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, f"concello_{id_concello}")},
            name=f"{const.INTEGRATION_NAME} {name}",
            manufacturer=const.INTEGRATION_NAME,
        )

    @property
    def is_on(self):
        """Return true when the service reports one or more warnings."""
        return bool(_warning_items(self.coordinator.data))

    @property
    def extra_state_attributes(self):
        """Expose all detailed warnings without discarding MeteoGalicia fields."""
        items = _warning_items(self.coordinator.data)
        levels = [
            item.get("idNivel")
            for item in items
            if isinstance(item.get("idNivel"), (int, float))
        ]
        return {
            "warning_count": len(items),
            "max_level": max(levels) if levels else 0,
            "warning_types": sorted(
                {
                    str(item.get("tipoalerta_es") or item.get("tipoalerta_gl"))
                    for item in items
                    if item.get("tipoalerta_es") or item.get("tipoalerta_gl")
                }
            ),
            "warnings": items,
        }
