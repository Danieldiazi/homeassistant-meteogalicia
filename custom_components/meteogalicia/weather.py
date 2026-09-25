"""Weather entity for the MeteoGalicia integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.weather import WeatherEntity, WeatherEntityFeature
from homeassistant.const import CONF_SCAN_INTERVAL, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import (
    MeteoGaliciaForecastCoordinator,
    MeteoGaliciaHourlyForecastCoordinator,
    MeteoGaliciaObservationCoordinator,
    async_get_entry_coordinator,
)

ATTRIBUTION = "Data provided by MeteoGalicia"

# MeteoGalicia forecast times are local Galician time without an offset.
_FORECAST_TIME_ZONE = ZoneInfo("Europe/Madrid")

# Wind codes 301-332 repeat the same eight directions for each intensity
# (light, moderate, strong, very strong): N, NE, E, SE, S, SW, W, NW.
# 299 (calm) and 300 (variable) have no direction.
_FIRST_DIRECTIONAL_WIND_CODE = 301
_LAST_DIRECTIONAL_WIND_CODE = 332

# MeteoGalicia uses the same final two digits for equivalent day/night icons:
# 1xx codes are daytime icons and 2xx codes are nighttime icons.
_CONDITION_BY_CODE = {
    1: "sunny",
    2: "partlycloudy",
    3: "partlycloudy",
    4: "cloudy",
    5: "cloudy",
    6: "fog",
    7: "rainy",
    8: "rainy",
    9: "snowy-rainy",
    10: "rainy",
    11: "rainy",
    12: "snowy",
    13: "lightning-rainy",
    14: "fog",
    15: "fog",
    16: "partlycloudy",
    17: "rainy",
    18: "rainy",
    19: "lightning-rainy",
    20: "snowy-rainy",
    21: "hail",
    22: "rainy",
    23: "snowy",
    24: "fog",
    25: "cloudy",
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
    condition = _CONDITION_BY_CODE.get(code % 100)
    if condition == "sunny" and 200 <= code < 300:
        return "clear-night"
    return condition


def _valid_value(value: Any) -> Any:
    """Return None for MeteoGalicia's unavailable sentinel."""
    return None if value == -9999 else value


def _wind_bearing_from_code(value: Any) -> float | None:
    """Translate a MeteoGalicia wind code to the direction it blows from."""
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    if not _FIRST_DIRECTIONAL_WIND_CODE <= code <= _LAST_DIRECTIONAL_WIND_CODE:
        return None
    return float((code - _FIRST_DIRECTIONAL_WIND_CODE) % 8 * 45)


def _now() -> datetime:
    """Return the current time in MeteoGalicia's forecast time zone."""
    return datetime.now(_FORECAST_TIME_ZONE)


def _forecast_hours(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract valid hourly forecast records."""
    if not isinstance(data, dict):
        return []
    pred_horaria = data.get("predHoraria")
    if not isinstance(pred_horaria, dict):
        return []
    days = pred_horaria.get("listaPredDiaHoraria")
    if not isinstance(days, list):
        return []
    hours = []
    for day in days:
        items = day.get("listaPredHora") if isinstance(day, dict) else None
        if isinstance(items, list):
            hours.extend(item for item in items if isinstance(item, dict))
    return hours


def _forecast_hour_start(item: dict[str, Any]) -> datetime | None:
    """Return the local start time of an hourly forecast record."""
    value = item.get("dataPredicion")
    if not isinstance(value, str):
        return None
    try:
        start = datetime.fromisoformat(value)
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=_FORECAST_TIME_ZONE)
    return start


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


def _current_observation(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract the latest measured municipal observation."""
    if not isinstance(data, dict):
        return None
    observations = data.get("listaObservacionConcellos")
    if not isinstance(observations, list) or not observations:
        return None
    observation = observations[0]
    return observation if isinstance(observation, dict) else None


def _observation_float(data: dict[str, Any] | None, key: str) -> float | None:
    """Return a numeric measured observation, ignoring unavailable values."""
    observation = _current_observation(data)
    if observation is None:
        return None
    value = observation.get(key)
    if value in (None, -9999):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _weather_unique_id(id_concello: str) -> str:
    """Return the stable unique id for a municipal weather entity."""
    return f"meteogalicia_weather_{id_concello}"


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up a MeteoGalicia weather entity from a config entry."""
    data = _merge_entry_data(entry)
    scan_interval = data.get(CONF_SCAN_INTERVAL)
    id_concello = data.get(const.CONF_ID_CONCELLO)
    if not id_concello:
        return

    coordinator = await async_get_entry_coordinator(
        hass,
        entry.entry_id,
        MeteoGaliciaForecastCoordinator,
        id_concello,
        scan_interval,
    )

    observation_coordinator = await async_get_entry_coordinator(
        hass,
        entry.entry_id,
        MeteoGaliciaObservationCoordinator,
        id_concello,
        scan_interval,
    )

    # The hourly forecast is optional: if it is unavailable the entity still
    # works and the hourly forecast is simply empty until the next refresh.
    hourly_coordinator = await async_get_entry_coordinator(
        hass,
        entry.entry_id,
        MeteoGaliciaHourlyForecastCoordinator,
        id_concello,
        scan_interval,
    )

    pred_concello = (coordinator.data or {}).get("predConcello")
    if not isinstance(pred_concello, dict) or not pred_concello.get("nome"):
        raise PlatformNotReady

    async_add_entities(
        [
            MeteoGaliciaWeather(
                pred_concello["nome"],
                id_concello,
                coordinator,
                observation_coordinator,
                hourly_coordinator,
            )
        ]
    )


class MeteoGaliciaWeather(CoordinatorEntity, WeatherEntity):
    """Municipal MeteoGalicia forecast."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        name: str,
        id_concello: str,
        coordinator,
        observation_coordinator,
        hourly_coordinator,
    ) -> None:
        super().__init__(coordinator)
        self._observation_coordinator = observation_coordinator
        self._hourly_coordinator = hourly_coordinator
        self._municipality_name = name
        self._id_concello = id_concello
        self._attr_unique_id = _weather_unique_id(id_concello)
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, f"concello_{id_concello}")},
            name=f"{const.INTEGRATION_NAME} {name}",
            manufacturer=const.INTEGRATION_NAME,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to measured-observation updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._observation_coordinator.async_add_listener(self.async_write_ha_state)
        )
        self.async_on_remove(
            self._hourly_coordinator.async_add_listener(
                self._handle_hourly_coordinator_update
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write the state and push the daily forecast to its subscribers."""
        super()._handle_coordinator_update()
        self._async_push_forecast("daily")

    @callback
    def _handle_hourly_coordinator_update(self) -> None:
        """Push the hourly forecast to its subscribers."""
        self._async_push_forecast("hourly")

    @callback
    def _async_push_forecast(self, forecast_type: str) -> None:
        """Send an updated forecast to the frontend cards that show it."""
        self.hass.async_create_task(self.async_update_listeners((forecast_type,)))

    @property
    def native_temperature(self) -> float | None:
        """Return the latest temperature actually observed for the municipality."""
        return _observation_float(self._observation_coordinator.data, "temperatura")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the latest apparent temperature actually observed."""
        return _observation_float(
            self._observation_coordinator.data, "sensacionTermica"
        )

    @property
    def condition(self) -> str | None:
        """Return the latest sky condition actually observed."""
        observation = _current_observation(self._observation_coordinator.data)
        return (
            _condition_from_code(observation.get("icoEstadoCeo"))
            if observation is not None
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the real observation time and whether it is stale."""
        coordinator = self._observation_coordinator
        attributes = {
            "observation_timestamp": getattr(coordinator, "data_timestamp", None),
            "observation_age_s": getattr(coordinator, "data_age_seconds", None),
            "observation_stale": getattr(coordinator, "data_is_stale", None),
        }
        return {key: value for key, value in attributes.items() if value is not None}

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
                    "uv_index": _valid_value(item.get("uvMax")),
                }
            )
        return forecast or None

    async def async_forecast_hourly(self) -> list[dict[str, Any]] | None:
        """Return the hourly forecast from the current hour onwards."""
        current_hour = _now().replace(minute=0, second=0, microsecond=0)
        forecast = []
        for item in _forecast_hours(self._hourly_coordinator.data):
            start = _forecast_hour_start(item)
            if start is None or start < current_hour:
                continue
            forecast.append(
                {
                    "datetime": start.isoformat(),
                    "condition": _condition_from_code(item.get("icoCeo")),
                    "native_temperature": _valid_value(item.get("tMedia")),
                    "wind_bearing": _wind_bearing_from_code(item.get("icoVento")),
                }
            )
        return forecast or None
