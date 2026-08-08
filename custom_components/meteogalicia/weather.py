"""Weather entity for the MeteoGalicia integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import CONF_SCAN_INTERVAL, UnitOfTemperature
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import const
from .coordinator import MeteoGaliciaForecastCoordinator

ATTRIBUTION = "Data provided by MeteoGalicia"

# MeteoGalicia uses the same final two digits for equivalent day/night icons.
_CONDITION_BY_CODE = {
    1: ATTR_CONDITION_SUNNY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_PARTLYCLOUDY,
    4: ATTR_CONDITION_CLOUDY,
    5: ATTR_CONDITION_CLOUDY,
    6: ATTR_CONDITION_FOG,
    7: ATTR_CONDITION_RAINY,
    8: ATTR_CONDITION_RAINY,
    9: ATTR_CONDITION_SNOWY_RAINY,
    10: ATTR_CONDITION_RAINY,
    11: ATTR_CONDITION_RAINY,
    12: ATTR_CONDITION_SNOWY,
    13: ATTR_CONDITION_LIGHTNING_RAINY,
    14: ATTR_CONDITION_FOG,
    15: ATTR_CONDITION_FOG,
    16: ATTR_CONDITION_PARTLYCLOUDY,
    17: ATTR_CONDITION_RAINY,
    18: ATTR_CONDITION_RAINY,
    19: ATTR_CONDITION_LIGHTNING_RAINY,
    20: ATTR_CONDITION_SNOWY_RAINY,
    21: ATTR_CONDITION_HAIL,
    22: ATTR_CONDITION_RAINY,
    23: ATTR_CONDITION_SNOWY,
    24: ATTR_CONDITION_FOG,
    25: ATTR_CONDITION_CLOUDY,
}


def _merge_entry_data(entry) -> dict[str, Any]:
    """Merge config entry data and options, allowing options to clear values."""
    data = dict(entry.data)
    for key, value in entry.options.items():
        if value in ("", None):
            data.pop(key, None)
        else:
            data[key] = value
    return data


def _condition_from_code(value: Any) -> str | None:
    """Translate a MeteoGalicia sky code to a Home Assistant condition."""
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    if code == -9999:
        return None
    return _CONDITION_BY_CODE.get(code % 100)


def _time_period() -> str:
    """Return the MeteoGalicia period for the current local time."""
    hour = dt_util.now().hour
    if 6 <= hour < 14:
        return "manha"
    if 14 <= hour < 21:
        return "tarde"
    return "noite"


def _valid_value(value: Any) -> Any:
    """Return None for MeteoGalicia's unavailable sentinel."""
    return None if value == -9999 else value


def _maximum_probability(item: dict[str, Any]) -> int | None:
    """Return the maximum valid rain probability for a forecast day."""
    probabilities = item.get("pchoiva")
    if not isinstance(probabilities, dict):
        return None
    values = [
        value
        for value in probabilities.values()
        if isinstance(value, (int, float)) and value >= 0
    ]
    return int(max(values)) if values else None


def _forecast_days(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract valid daily forecast records."""
    if not isinstance(data, dict):
        return []
    pred_concello = data.get("predConcello")
    if not isinstance(pred_concello, dict):
        return []
    days = pred_concello.get("listaPredDiaConcello")
    return days if isinstance(days, list) else []


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up a MeteoGalicia weather entity from a config entry."""
    data = _merge_entry_data(entry)
    id_concello = data.get(const.CONF_ID_CONCELLO)
    if not id_concello:
        return

    coordinator = MeteoGaliciaForecastCoordinator(
        hass,
        id_concello,
        entry.options.get(CONF_SCAN_INTERVAL),
    )
    coordinators = (
        hass.data.setdefault(const.DOMAIN, {})
        .setdefault(entry.entry_id, {})
        .setdefault("coordinators", [])
    )
    coordinators.append(coordinator)
    await coordinator.async_config_entry_first_refresh()

    pred_concello = (coordinator.data or {}).get("predConcello")
    if not isinstance(pred_concello, dict) or not pred_concello.get("nome"):
        raise PlatformNotReady

    async_add_entities(
        [
            MeteoGaliciaWeather(
                pred_concello["nome"],
                id_concello,
                coordinator,
            )
        ]
    )


class MeteoGaliciaWeather(CoordinatorEntity, WeatherEntity):
    """Municipal MeteoGalicia forecast."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, name: str, id_concello: str, coordinator) -> None:
        super().__init__(coordinator)
        self._municipality_name = name
        self._id_concello = id_concello
        self._attr_unique_id = f"meteogalicia_weather_{id_concello}"
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, f"concello_{id_concello}")},
            name=f"{const.INTEGRATION_NAME} {name}",
            manufacturer=const.INTEGRATION_NAME,
        )

    @property
    def condition(self) -> str | None:
        """Return the condition for the current part of today."""
        days = _forecast_days(self.coordinator.data)
        if not days:
            return None
        sky = days[0].get("ceo")
        if isinstance(sky, dict):
            return _condition_from_code(sky.get(_time_period()))
        return _condition_from_code(days[0].get("ceoDia"))

    async def async_forecast_daily(self) -> list[dict[str, Any]] | None:
        """Return the daily forecast."""
        forecast = []
        for item in _forecast_days(self.coordinator.data):
            forecast.append(
                {
                    "datetime": item.get("dataPredicion"),
                    "condition": _condition_from_code(item.get("ceoDia")),
                    "native_temperature": _valid_value(item.get("tMax")),
                    "native_templow": _valid_value(item.get("tMin")),
                    "precipitation_probability": _maximum_probability(item),
                    "native_uv_index": _valid_value(item.get("uvMax")),
                }
            )
        return forecast or None
