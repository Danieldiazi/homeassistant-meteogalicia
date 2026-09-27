# -*- coding: utf-8 -*-
"""Módulo de sensores para la integración MeteoGalicia."""
import logging
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    DEGREE,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from . import const
from .intervals import get_scan_interval, merge_entry_data
from .coordinator import (
    MeteoGaliciaForecastCoordinator,
    MeteoGaliciaMaxWarningLevelsCoordinator,
    MeteoGaliciaObservationCoordinator,
    MeteoGaliciaStationDailyCoordinator,
    MeteoGaliciaStationLast10MinCoordinator,
    async_get_entry_coordinator,
)

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by MeteoGalicia"
_FORECAST_TIME_ZONE = ZoneInfo("Europe/Madrid")


def _base_attrs(entity_id: str) -> dict:
    """Crea atributos base comunes."""
    return {
        const.ATTR_INFORMATION: [],
        const.ATTR_INTEGRATION: const.DOMAIN,
        const.ATTR_ID: entity_id,
    }


def _build_device_info(domain_key: str, name: str) -> DeviceInfo:
    """Construye DeviceInfo común."""
    return DeviceInfo(
        identifiers={(const.DOMAIN, domain_key)},
        name=f"{const.INTEGRATION_NAME} {name}",
        manufacturer=const.INTEGRATION_NAME,
    )


class MeteoGaliciaExtraAttrsMixin:
    """Mixin para exponer atributos extra compartidos."""

    @property
    def extra_state_attributes(self):
        base_attr = getattr(self, "_attr", {}) or {}
        attributes = {
            **base_attr,
            const.ATTR_CONNECTED_AT: _get_coordinator_connected_at(self.coordinator),
            const.ATTR_API_LATENCY_MS: _get_coordinator_api_latency_ms(self.coordinator),
            const.ATTR_SCAN_INTERVAL_S: _get_coordinator_scan_interval(self.coordinator),
        }
        if (timestamp := getattr(self.coordinator, "data_timestamp", None)) is not None:
            attributes[const.ATTR_DATA_TIMESTAMP] = timestamp
            attributes[const.ATTR_DATA_AGE_S] = getattr(
                self.coordinator, "data_age_seconds", None
            )
            attributes[const.ATTR_DATA_STALE] = getattr(
                self.coordinator, "data_is_stale", None
            )
        return attributes


def _get_coordinator_connected_at(coordinator) -> str:
    """Devuelve la última actualización exitosa del coordinador en ISO UTC."""
    connected_at = getattr(coordinator, "last_api_connected_at", None)
    if connected_at:
        return connected_at.isoformat() if hasattr(connected_at, "isoformat") else str(connected_at)
    return STATE_UNKNOWN


def _get_coordinator_api_latency_ms(coordinator) -> float | str:
    """Devuelve la última latencia de API en milisegundos."""
    for attr_name in ("last_api_latency_ms", "last_api_latency"):
        latency = getattr(coordinator, attr_name, None)
        if latency is None:
            continue
        try:
            return float(latency)
        except (TypeError, ValueError):
            return STATE_UNKNOWN
    return STATE_UNKNOWN


def _get_coordinator_scan_interval(coordinator) -> float | str:
    """Devuelve el scan_interval aplicado en segundos."""
    update_interval = getattr(coordinator, "update_interval", None)
    if update_interval is None:
        return STATE_UNKNOWN
    try:
        return float(update_interval.total_seconds())
    except Exception:
        return STATE_UNKNOWN


# Obtaining config from configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    { vol.Optional(const.CONF_ID_CONCELLO): cv.string,
      vol.Optional(const.CONF_ID_ESTACION): cv.string,
      vol.Optional(const.CONF_ID_ESTACION_MEDIDA_DAILY): cv.string,
      vol.Optional(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN): cv.string,
      # Do not insert HA's generic polling default into a legacy YAML import.
      vol.Optional(CONF_SCAN_INTERVAL): cv.positive_time_period,}
    
)

_YAML_IMPORT_KEYS = (
    const.CONF_ID_CONCELLO,
    const.CONF_ID_ESTACION,
    const.CONF_ID_ESTACION_MEDIDA_DAILY,
    const.CONF_ID_ESTACION_MEDIDA_LAST10MIN,
    CONF_SCAN_INTERVAL,
)


def _yaml_import_data(config: dict) -> dict:
    """Return serializable config-entry data from a legacy YAML block."""
    data = {
        key: config[key]
        for key in _YAML_IMPORT_KEYS
        if config.get(key) is not None
    }
    scan_interval = data.get(CONF_SCAN_INTERVAL)
    if hasattr(scan_interval, "total_seconds"):
        data[CONF_SCAN_INTERVAL] = int(scan_interval.total_seconds())
    return data


def _yaml_configuration(data: dict) -> str:
    """Render the imported YAML block for the Repairs notification."""
    lines = ["sensor:", "  - platform: meteogalicia"]
    for key in _YAML_IMPORT_KEYS:
        if key in data:
            lines.append(f"    {key}: {data[key]}")
    return "\n".join(lines)


def _yaml_issue_id(data: dict) -> str:
    """Return one stable Repairs issue ID per imported YAML block."""
    parts = [str(data.get(key, "")) for key in _YAML_IMPORT_KEYS[:-1]]
    suffix = re.sub(r"[^a-zA-Z0-9_-]+", "_", "_".join(parts)).strip("_")
    return f"yaml_imported_{suffix}"


def _create_yaml_import_issue(hass, data: dict) -> None:
    """Tell the user which successfully imported YAML block can be removed."""
    identifier = data.get(const.CONF_ID_CONCELLO) or data.get(const.CONF_ID_ESTACION)
    ir.async_create_issue(
        hass,
        const.DOMAIN,
        _yaml_issue_id(data),
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_imported",
        translation_placeholders={
            "configuration": _yaml_configuration(data),
            "identifier": str(identifier),
        },
    )


def _validate_id(value: str, expected_len: int) -> bool:
    """Valida que el id tenga longitud y sea numérico."""
    return isinstance(value, str) and len(value) == expected_len and value.isnumeric()


async def async_setup_platform(hass, config, _add_entities, _discovery_info=None):  # pylint: disable=missing-docstring, unused-argument
    """Import a legacy YAML sensor block into a config entry."""
    data = _yaml_import_data(config)
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=data,
    )
    if result.get("reason") != "invalid_import":
        _create_yaml_import_issue(hass, data)


async def async_setup_entry(hass, entry, add_entities):
    """Configura sensores de MeteoGalicia desde una entrada de configuración."""
    data = merge_entry_data(entry)
    scan_interval = get_scan_interval(data, const.CONF_OBSERVATION_INTERVAL)
    coordinators = (
        hass.data.setdefault(const.DOMAIN, {})
        .setdefault(entry.entry_id, {})
        .setdefault("coordinators", [])
    )

    if data.get(const.CONF_ID_CONCELLO, ""):
        id_concello = data[const.CONF_ID_CONCELLO]
        await setup_id_concello_platform(
            id_concello,
            add_entities,
            hass,
            scan_interval,
            coordinators,
            entry.entry_id,
            warnings_enabled=data.get(const.CONF_WARNINGS_ENABLED, False),
            forecast_scan_interval=get_scan_interval(
                data, const.CONF_FORECAST_INTERVAL
            ),
        )
    elif data.get(const.CONF_ID_ESTACION, ""):
        id_estacion = data[const.CONF_ID_ESTACION]
        await setup_id_estacion_platform(
            id_estacion,
            data,
            add_entities,
            hass,
            data.get(CONF_SCAN_INTERVAL),
            coordinators,
        )


async def setup_id_estacion_platform(
    id_estacion, config, add_entities, hass, scan_interval, coordinators=None
):
    """Configura la plataforma de estación y añade los sensores correspondientes."""
    interval_data = {CONF_SCAN_INTERVAL: scan_interval, **config}
    id_measure_daily = config.get(const.CONF_ID_ESTACION_MEDIDA_DAILY) or None
    id_measure_last10min = config.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN) or None

    if not _validate_id(id_estacion, 5):
        _LOGGER.debug(
            "%s Configurado (YAML) 'id_estacion' '%s' no es válido",
            const.LOG_PREFIX,
            id_estacion,
        )
        return False

    entities = []
    station_coordinators = []
    if id_measure_daily is not None or id_measure_last10min is None:
        daily_coordinator = await _async_setup_sensor_coordinator(
            hass,
            MeteoGaliciaStationDailyCoordinator,
            id_estacion,
            get_scan_interval(interval_data, const.CONF_STATION_DAILY_INTERVAL),
            coordinators,
        )
        station_coordinators.append(daily_coordinator)
        entities.extend(
            _station_summary_and_measures(
                id_estacion,
                id_measure_daily,
                daily_coordinator,
                MeteoGaliciaDailyDataByStationSensor,
                "daily",
            )
        )

    if id_measure_last10min is not None or id_measure_daily is None:
        last10min_coordinator = await _async_setup_sensor_coordinator(
            hass,
            MeteoGaliciaStationLast10MinCoordinator,
            id_estacion,
            get_scan_interval(interval_data, const.CONF_OBSERVATION_INTERVAL),
            coordinators,
        )
        station_coordinators.append(last10min_coordinator)
        entities.extend(
            _station_summary_and_measures(
                id_estacion,
                id_measure_last10min,
                last10min_coordinator,
                MeteoGaliciaLast10MinDataByStationSensor,
                "last_10_min",
            )
        )

    add_entities(entities)
    for coordinator in station_coordinators:
        coordinator.async_set_updated_data(coordinator.data)


async def _async_setup_sensor_coordinator(
    hass, coordinator_class, resource_id, scan_interval, coordinators, entry_id=None
):
    """Reuse an entry coordinator or register and refresh a standalone one."""
    if entry_id is not None:
        return await async_get_entry_coordinator(
            hass, entry_id, coordinator_class, resource_id, scan_interval
        )
    coordinator = coordinator_class(hass, resource_id, scan_interval)
    if coordinators is not None:
        coordinators.append(coordinator)
    await coordinator.async_refresh()
    return coordinator


def _station_summary_and_measures(
    station_id, measure_id, coordinator, summary_class, period
):
    """Keep the legacy summary and expose all measures when none was selected."""
    entities = [summary_class(station_id, station_id, measure_id, coordinator)]
    if measure_id is None:
        entities.extend(_station_measure_entities(station_id, coordinator, period))
    _LOGGER.info(
        "%s Añadidos datos %s para la estación '%s' - medida principal: %s",
        const.LOG_PREFIX,
        period,
        station_id,
        measure_id,
    )
    return entities


async def setup_id_concello_platform(
    id_concello,
    add_entities,
    hass,
    scan_interval,
    coordinators=None,
    entry_id=None,
    warnings_enabled=False,
    forecast_scan_interval=None,
):
    """Configura la plataforma de concello y añade los sensores correspondientes."""
    if forecast_scan_interval is None:
        forecast_scan_interval = scan_interval
    # id_concello must to have 5 chars and be a number
    if not _validate_id(id_concello, 5):
        _LOGGER.critical(
            "%s Configurado (YAML) 'id_concello' '%s' no es válido",
            const.LOG_PREFIX,
            id_concello,
        )
        return False
    forecast_coordinator = await _async_setup_sensor_coordinator(
        hass,
        MeteoGaliciaForecastCoordinator,
        id_concello,
        forecast_scan_interval,
        coordinators,
        entry_id,
    )
    if (
        not forecast_coordinator.last_update_success
        or not forecast_coordinator.data
        or not forecast_coordinator.data.get("predConcello")
    ):
        raise PlatformNotReady

    name = forecast_coordinator.data["predConcello"].get("nome")
    if not name:
        raise PlatformNotReady

    observation_coordinator = await _async_setup_sensor_coordinator(
        hass,
        MeteoGaliciaObservationCoordinator,
        id_concello,
        scan_interval,
        coordinators,
        entry_id,
    )

    forecast_temperature_by_day_sensor_config = [
        ("Today", 0, "tMax"),
        ("Today", 0, "tMin"),
        ("Tomorrow", 1, "tMax"),
        ("Tomorrow", 1, "tMin"),
    ]

    entities = []
    for item_sensor_config in forecast_temperature_by_day_sensor_config:
        entities.append(
            MeteoGaliciaForecastTemperatureByDaySensor(
                name,
                id_concello,
                item_sensor_config[0],
                item_sensor_config[1],
                item_sensor_config[2],
                forecast_coordinator,
            )
        )
        _LOGGER.info(
            "%s Añadido sensor de temperatura %s %s para '%s' con id '%s'",
            const.LOG_PREFIX,
            item_sensor_config[0],
            item_sensor_config[2],
            name,
            id_concello,
        )

    entities.append(
        MeteoGaliciaForecastRainByDaySensor(
            name, id_concello, "Today", 0, False, forecast_coordinator
        )
    )
    _LOGGER.info(
        "%s Añadido sensor de probabilidad de lluvia para hoy en '%s' con id '%s'",
        const.LOG_PREFIX,
        name,
        id_concello,
    )
    entities.append(
        MeteoGaliciaForecastRainByDaySensor(
            name, id_concello, "Tomorrow", 1, True, forecast_coordinator
        )
    )
    _LOGGER.info(
        "%s Añadido sensor de probabilidad de lluvia para mañana en '%s' con id '%s'",
        const.LOG_PREFIX,
        name,
        id_concello,
    )

    if warnings_enabled:
        warnings_level_coordinator = await _async_setup_sensor_coordinator(
            hass,
            MeteoGaliciaMaxWarningLevelsCoordinator,
            id_concello,
            scan_interval,
            coordinators,
            entry_id,
        )

        for day_index, day_name in enumerate(
            ("today", "tomorrow", "day_after_tomorrow")
        ):
            entities.append(
                MeteoGaliciaWarningLevelSensor(
                    name,
                    id_concello,
                    day_index,
                    day_name,
                    warnings_level_coordinator,
                )
            )

    entities.append(
        MeteoGaliciaTemperatureSensor(name, id_concello, observation_coordinator)
    )
    _LOGGER.info(
        "%s Añadido sensor de temperatura para '%s' con id '%s'",
        const.LOG_PREFIX,
        name,
        id_concello,
    )
    add_entities(entities)
    forecast_coordinator.async_set_updated_data(forecast_coordinator.data)
    observation_coordinator.async_set_updated_data(observation_coordinator.data)


_WARNING_LEVEL_NAMES = {
    0: "normal",
    1: "yellow",
    2: "orange",
    3: "red",
}


class MeteoGaliciaWarningLevelSensor(
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):
    """Maximum MeteoGalicia warning level for one forecast day."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, name, idc, day_index, day_name, coordinator):
        super().__init__(coordinator)
        self._name = name
        self.id = idc
        self._day_index = day_index
        self._day_name = day_name
        self._attr_translation_key = f"warning_level_{day_name}"
        self._attr_unique_id = f"meteogalicia_{idc}_warning_level_{day_name}"
        self._attr_device_info = _build_device_info(f"concello_{idc}", name)

    def _warning_level_item(self):
        """Find this municipality's level by forecast day, independent of order."""
        data = self.coordinator.data or {}
        days = data.get("listaDiaConcellos") if isinstance(data, dict) else None
        if not isinstance(days, list):
            return None
        for day in days:
            if not isinstance(day, dict) or day.get("dia") != self._day_index:
                continue
            items = day.get("listaNiveisMaximos")
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and str(item.get("idConcello")) == str(self.id):
                    return item
        return None

    @property
    def native_value(self):
        """Return MeteoGalicia's maximum level for this day."""
        item = self._warning_level_item()
        if item is None:
            return None
        try:
            level = int(item.get("nivelMax"))
        except (TypeError, ValueError):
            return None
        return _WARNING_LEVEL_NAMES.get(level, str(level))

    @property
    def extra_state_attributes(self):
        """Expose numeric warning level together with coordinator metadata."""
        attrs = super().extra_state_attributes
        item = self._warning_level_item()
        if item is not None:
            attrs = {**attrs, "level": item.get("nivelMax")}
        return attrs

    @property
    def icon(self):
        return "mdi:alert"


# Sensor Class
def _forecast_day(data, day_offset):
    """Select a dated forecast; yesterday's first row is no longer today's."""
    target = (dt.now(_FORECAST_TIME_ZONE).date() + timedelta(days=day_offset)).isoformat()
    forecast = data.get("predConcello") if isinstance(data, dict) else None
    days = forecast.get("listaPredDiaConcello") if isinstance(forecast, dict) else None
    if not isinstance(days, list):
        return None
    return next(
        (
            item for item in days
            if isinstance(item, dict)
            and isinstance(item.get("dataPredicion"), str)
            and item["dataPredicion"][:10] == target
        ),
        None,
    )


class ForecastTimeMixin:
    """Refresh dates and rain time slots locally between scheduled downloads."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._update_from_data(self.coordinator.data)
        self.async_on_remove(
            async_track_utc_time_change(
                self.hass, self._refresh_forecast_time, minute=0, second=0
            )
        )

    @callback
    def _refresh_forecast_time(self, _now) -> None:
        self._handle_coordinator_update()


class MeteoGaliciaForecastTemperatureByDaySensor(
    ForecastTimeMixin, MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor de temperatura prevista por día."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        name,
        idc,
        forecast_name,
        forecast_day,
        forecast_field,
        coordinator,
    ):
        super().__init__(coordinator)
        self._name = name
        self.id = idc
        self.forecast_name = forecast_name
        self.forecast_day = forecast_day
        self.forecast_field = forecast_field
        self._state = None
        self._attr = {}
        if self.forecast_field == "tMax":
            self.forecast_field_name = const.FORECAST_MAX_TEMPERATURE
        elif self.forecast_field == "tMin":
            self.forecast_field_name = const.FORECAST_MIN_TEMPERATURE
        else:
            self.forecast_field_name = f"{self.forecast_field} no definido"

    def _update_from_data(self, data) -> None:
        if not self.coordinator.last_update_success:
            self._state = None
            self._attr = {}
            return
        if not data or data.get("predConcello") is None:
            self._state = None
            self._attr = {}
            return

        item = _forecast_day(data, self.forecast_day)
        if item is None:
            self._state = None
            self._attr = {}
            return
        state = item.get(self.forecast_field, "null")
        if state == -9999:
            state = None

        self._state = state
        self._attr = {
            **_base_attrs(self.id),
            const.ATTR_FORECAST_DATE: item.get("dataPredicion"),
        }

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Devuelve el nombre."""
        return f"{self._name} - {self.forecast_field_name} - {self.forecast_name} "

    @property
    def unique_id(self) -> str:
        """Devuelve un ID único para este sensor."""

        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{self.forecast_field_name.lower()}_{self.id}".replace(
            ",", ""
        )

    @property
    def icon(self):
        """Devuelve el icono."""
        return "mdi:thermometer"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(f"concello_{self.id}", self._name)

    @property
    def device_class(self) -> str:
        """Devuelve la clase de dispositivo."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Devuelve el estado del sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Devuelve la unidad de medida."""
        return UnitOfTemperature.CELSIUS


class MeteoGaliciaForecastRainByDaySensor(
    ForecastTimeMixin, MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor de probabilidad de lluvia por día."""
    _attr_attribution = ATTRIBUTION

    def __init__(self, name, idc, forecast_name, forecast_day, max_value, coordinator):
        super().__init__(coordinator)
        self._name = name
        self.id = idc
        self.forecast_name = forecast_name
        self.forecast_day = forecast_day
        self.max_value = max_value
        self._state = None
        self._attr = {}

    def _update_from_data(self, data) -> None:
        if not self.coordinator.last_update_success:
            self._state = None
            self._attr = {}
            return
        if not data or data.get("predConcello") is None:
            self._state = None
            self._attr = {}
            return

        item = _forecast_day(data, self.forecast_day)
        if item is None:
            self._state = None
            self._attr = {}
            return
        pchoiva = item.get("pchoiva")
        if not isinstance(pchoiva, dict):
            pchoiva = {}

        state = get_state_forecast_rain_by_day_sensor(self.max_value, item)

        self._state = state
        self._attr = {
            **_base_attrs(self.id),
            const.ATTR_FORECAST_DATE: item.get("dataPredicion"),
            const.ATTR_RAIN_PROB_NOON: pchoiva.get("manha"),
            const.ATTR_RAIN_PROB_AFTERNOON: pchoiva.get("tarde"),
            const.ATTR_RAIN_PROB_NIGHT: pchoiva.get("noite"),
        }

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Devuelve el nombre."""
        return f"{self._name} - {const.FORECAST_RAIN_PROBABILITY} - {self.forecast_name}"

    @property
    def unique_id(self) -> str:
        """Devuelve un ID único para este sensor."""
        unique_id = f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_RAIN_PROBABILITY.lower()}_{self.id}"
        unique_id = unique_id.replace(",", "")
        return unique_id

    @property
    def icon(self):
        """Devuelve el icono."""
        return "mdi:percent"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(f"concello_{self.id}", self._name)

    @property
    def native_value(self):
        """Devuelve el estado del sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Devuelve la unidad de medida."""
        return PERCENTAGE


# Sensor Class
class MeteoGaliciaTemperatureSensor(
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor de temperatura observada."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, name, idc, coordinator):
        super().__init__(coordinator)
        self._name = name
        self.id = idc
        self._state = None
        self._attr = {}

    def _update_from_data(self, data) -> None:
        if not self.coordinator.last_update_success:
            self._state = None
            self._attr = {}
            return
        if not data or data.get("listaObservacionConcellos") is None:
            self._state = None
            self._attr = {}
            return

        item = _get_first_list_item(data, "listaObservacionConcellos")
        if item is None:
            self._state = None
            self._attr = {}
            return

        self._state = item.get("temperatura", "null")
        self._attr = {
            **_base_attrs(self.id),
            "local_date": item.get("dataLocal"),
            "utc_date": item.get("dataUTC"),
            "temperature_feeling": item.get("sensacionTermica"),
            "reference": item.get("nomeConcello"),
        }

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Devuelve el nombre."""
        return f"{self._name} - Temperature"

    @property
    def unique_id(self) -> str:
        """Devuelve un ID único para este sensor."""
        return f"meteogalicia_{self._name.lower()}_temperature_{self.id}".replace(
            ",", ""
        )

    @property
    def icon(self):
        """Devuelve el icono."""
        return "mdi:thermometer"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(f"concello_{self.id}", self._name)

    @property
    def state_class(self) -> SensorStateClass:
        """Devuelve la clase de estado del sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self) -> str:
        """Devuelve la clase de dispositivo."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Devuelve el estado del sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Devuelve la unidad de medida."""
        return UnitOfTemperature.CELSIUS








def get_state_forecast_rain_by_day_sensor(max_value: bool, item: dict) -> int | None:
    """Obtiene el valor de estado correcto para la lluvia prevista."""
    pchoiva = item.get("pchoiva")
    if not isinstance(pchoiva, dict):
        return None

    if max_value:
        # Si max_value es True, se elige el valor máximo disponible.
        values = [pchoiva.get("manha"), pchoiva.get("tarde"), pchoiva.get("noite")]
        values = [value for value in values if value is not None]
        if not values:
            return None
        state = max(values)
    else:
        # Si max_value es False, se usa el tramo horario actual.
        field = "manha"  # tramo mañana: 6-14 h
        hour = dt.now(_FORECAST_TIME_ZONE).hour
        if hour >= 21:
            field = "noite"  # tramo noche: 21-6 h
        elif hour >= 14:
            field = "tarde"  # tramo tarde: 14-21 h
        elif hour < 6:
            field = "noite"  # tramo noche: 21-6 h
        state = pchoiva.get(field)

    if state is not None and state < 0:
        # A veces el servicio devuelve -9999 si el dato no está disponible.
        state = None
    return state




class BaseStationSensor(MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity):
    """Base para sensores de estaci?n (diarios y ?ltimos 10 minutos)."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, name, ids, id_measure, coordinator, name_suffix_label: str):
        super().__init__(coordinator)
        self._name = name
        self.id = ids
        self.id_measure = id_measure
        self._state = None
        self._attr = {}
        self.name_suffix = "" if id_measure is None else f"_{id_measure}"
        self.measure_unit = None
        self._name_suffix_label = name_suffix_label

    def _extract_source(self, data):
        """Debe devolver (station, lista_medidas, extra_attr_dict, warning_message or None)."""
        raise NotImplementedError

    def _update_from_data(self, data) -> None:
        if not self.coordinator.last_update_success:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            return

        station, lista_medidas, extra_attrs, warning_msg = self._extract_source(data)
        if station is None:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            if warning_msg:
                _LOGGER.warning(warning_msg, self.id)
            return

        self._attr = {**_base_attrs(self.id), **extra_attrs}
        self._name = station.get("estacion", self._name)
        _apply_station_measures(self, lista_medidas)

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Devuelve el nombre."""
        return f"{self._name} - {self.name_suffix} - {self._name_suffix_label}"

    @property
    def unique_id(self) -> str:
        """Devuelve un ID ?nico para este sensor."""
        return (
            f"meteogalicia_{self.id}_{self._name_suffix_label.lower().replace(' ', '_')}"
            f"_{self.name_suffix.lower()}_{self.id}"
        ).replace(",", "")

    @property
    def icon(self):
        """Devuelve el icono."""
        return "mdi:information"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(f"station_{self.id}", self._name)

    @property
    def native_value(self):
        """Devuelve el estado del sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Devuelve la unidad de medida."""
        return self.measure_unit


class MeteoGaliciaDailyDataByStationSensor(BaseStationSensor):  # pylint: disable=missing-docstring
    """Sensor de datos diarios por estaci?n."""

    def __init__(self, name, ids, id_measure, coordinator):
        super().__init__(name, ids, id_measure, coordinator, "Station Daily Data")

    def _extract_source(self, data):
        item = _get_first_list_item(data, "listDatosDiarios")
        if item is None:
            return None, None, None, (
                "No se pueden descargar los datos solicitados de MeteoGalicia: el id de estaci?n %s no existe o hay un posible problema de conexi?n."
            )
        station = _get_first_list_item(item, "listaEstacions")
        if station is None:
            return None, None, None, None
        lista_medidas = station.get("listaMedidas")
        extra = {
            "data": item.get("data"),
            "concello": station.get("concello"),
            "estacion": station.get("estacion"),
        }
        return station, lista_medidas, extra, None


class MeteoGaliciaLast10MinDataByStationSensor(BaseStationSensor):  # pylint: disable=missing-docstring
    """Sensor de datos de los ?ltimos 10 minutos por estaci?n."""

    def __init__(self, name, ids, id_measure, coordinator):
        super().__init__(name, ids, id_measure, coordinator, "Station Last 10 min Data")

    def _extract_source(self, data):
        item = _get_first_list_item(data, "listUltimos10min")
        if item is None:
            return None, None, None, (
                "No se pueden descargar los datos solicitados de MeteoGalicia: el id de estaci?n %s no existe o hay un posible problema de conexi?n."
            )
        lista_medidas = item.get("listaMedidas")
        extra = {
            "instanteLecturaUTC": item.get("instanteLecturaUTC"),
            "idEstacion": item.get("idEstacion"),
            "estacion": item.get("estacion"),
        }
        return item, lista_medidas, extra, None


_STATION_SOURCE_CONFIG = {
    "daily": {
        "translation_key": "station_measure_daily",
        "payload_key": "listDatosDiarios",
    },
    "last_10_min": {
        "translation_key": "station_measure_last_10_min",
        "payload_key": "listUltimos10min",
    },
}


def _station_source(data: dict, source: str) -> tuple[dict | None, list[dict]]:
    """Return the station record and measures for one API source."""
    source_config = _STATION_SOURCE_CONFIG[source]
    item = _get_first_list_item(data, source_config["payload_key"])
    if item is None:
        return None, []
    station = (
        _get_first_list_item(item, "listaEstacions")
        if source == "daily"
        else item
    )
    if not isinstance(station, dict):
        return None, []
    measures = station.get("listaMedidas")
    return station, measures if isinstance(measures, list) else []


def _normalise_station_unit(unit: str | None) -> str | None:
    """Convert MeteoGalicia unit spellings to Home Assistant native units."""
    return {
        "ºC": UnitOfTemperature.CELSIUS,
        "°C": UnitOfTemperature.CELSIUS,
        "º": DEGREE,
        "°": DEGREE,
        "L/m2": UnitOfPrecipitationDepth.MILLIMETERS,
        "L/m²": UnitOfPrecipitationDepth.MILLIMETERS,
        "hPa": UnitOfPressure.HPA,
        "m/s": UnitOfSpeed.METERS_PER_SECOND,
        "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "W/m2": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        "W/m²": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    }.get(unit, unit)


def _station_measure_device_class(code: str) -> SensorDeviceClass | None:
    """Map well-known MeteoGalicia parameter families to HA device classes."""
    prefix = code.split("_", 1)[0]
    return {
        "HR": SensorDeviceClass.HUMIDITY,
        "PP": SensorDeviceClass.PRECIPITATION,
        "PR": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "PRED": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "RD": SensorDeviceClass.IRRADIANCE,
        "RS": SensorDeviceClass.IRRADIANCE,
        "TA": SensorDeviceClass.TEMPERATURE,
        "TO": SensorDeviceClass.TEMPERATURE,
        "TS": SensorDeviceClass.TEMPERATURE,
        "VV": SensorDeviceClass.WIND_SPEED,
    }.get(prefix)


def _station_measure_description(
    measure: dict, source: str
) -> SensorEntityDescription:
    """Build a typed description for a station measure returned by the API."""
    code = str(measure.get("codigoParametro") or "unknown")
    name = str(measure.get("nomeParametro") or code)
    return SensorEntityDescription(
        key=f"{source}_{code}",
        translation_key=_STATION_SOURCE_CONFIG[source]["translation_key"],
        translation_placeholders={"measure": name},
        native_unit_of_measurement=_normalise_station_unit(measure.get("unidade")),
        device_class=_station_measure_device_class(code),
        state_class=(
            SensorStateClass.TOTAL
            if "_SUM_" in code
            else SensorStateClass.MEASUREMENT
        ),
    )


def _valid_station_measure_value(measure: dict | None):
    """Return only original or interpolated station measurements."""
    if not isinstance(measure, dict):
        return None
    value = measure.get("valor")
    if measure.get("lnCodigoValidacion") not in (1, 5) or value == -9999:
        return None
    return value


class MeteoGaliciaStationMeasureSensor(
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):
    """One typed Home Assistant entity for one station measurement."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, station_id, station_name, source, measure, coordinator):
        self.entity_description = _station_measure_description(measure, source)
        super().__init__(coordinator)
        self._station_id = station_id
        self._source = source
        self._measure_code = str(measure.get("codigoParametro"))
        self._attr_unique_id = (
            f"meteogalicia_station_{station_id}_{source}_{self._measure_code}"
        )
        self._attr_device_info = _build_device_info(
            f"station_{station_id}", station_name
        )
        self._attr = _base_attrs(station_id)

    @property
    def available(self) -> bool:
        """Return whether the coordinator and this measurement are available."""
        return self.coordinator.last_update_success and self.native_value is not None

    @property
    def native_value(self):
        """Return the current value for this entity's measure code."""
        _, measures = _station_source(self.coordinator.data, self._source)
        measure = next(
            (
                item
                for item in measures
                if item.get("codigoParametro") == self._measure_code
            ),
            None,
        )
        return _valid_station_measure_value(measure)


def _station_measure_entities(station_id, coordinator, source):
    """Create one entity per distinct measure while preserving legacy sensors."""
    station, measures = _station_source(coordinator.data, source)
    if station is None:
        return []
    station_name = station.get("estacion", station_id)
    entities = []
    seen_codes = set()
    for measure in measures:
        code = measure.get("codigoParametro")
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        entities.append(
            MeteoGaliciaStationMeasureSensor(
                station_id, station_name, source, measure, coordinator
            )
        )
    return entities




def _get_first_list_item(container: dict, list_key: str):
    """Devuelve el primer elemento de una lista en un dict o None si falta."""
    if not isinstance(container, dict):
        return None
    items = container.get(list_key)
    if not items:
        return None
    return items[0]


def _apply_station_measures(entity, lista_medidas: list[dict]):
    """Rellena atributos, estado y unidad a partir de las medidas de la estación."""
    if not lista_medidas:
        entity._state = None
        entity.measure_unit = None
        return
    entity._attr = add_attributes_from_measures(lista_medidas, entity._attr)
    entity._state = get_state_station_sensor(entity.id_measure, entity._attr, entity.id)
    entity.measure_unit = get_measure_unit_station_sensor(entity.id_measure, entity._attr, entity.id)




def get_state_station_sensor(id_measure: str | None, attributes: dict, id_station: str):
    """Obtiene el valor de estado para un sensor de estación."""
    state = "Available"
    if (id_measure is not None):
        if id_measure+"_value" in attributes:
            state = attributes[id_measure+"_value"]
        else: #Measure for this sensor is unavailable
            state = None
            _LOGGER.warning(const.STRING_MEASURE_NOT_AVAILABLE, id_measure,id_station)
    return state

def get_measure_unit_station_sensor(id_measure: str | None, attributes: dict, id_station: str):
    """Obtiene la unidad de medida para un sensor de estación."""
    measure_unit = None
    if (id_measure is not None):
        value_key = id_measure + "_value"
        unit_key = id_measure + "_unit"
        if unit_key in attributes:
            measure_unit = attributes[unit_key]
        elif value_key in attributes:
            _LOGGER.warning(
                "Unidad de medida no disponible para '%s' en la estación '%s'",
                id_measure,
                id_station,
            )
        else: #Measure for this sensor is unavailable
            measure_unit = None
            _LOGGER.warning(const.STRING_MEASURE_NOT_AVAILABLE, id_measure,id_station)
    return measure_unit


def add_attributes_from_measures(lista_medidas: list[dict], attributes: dict) -> dict:
    """Añade atributos desde las medidas recibidas para un sensor de estación."""
    attr = attributes
    for medida in lista_medidas:
        #Chequeo si el dato recogido es válido o no.
        #En la documentación 1 es dato valido original, y 5 dato valido interpolado
        #Si el valor es -9999 es un valor inválido, por lo que no devolvemos el valor del atributo
        if (medida.get("lnCodigoValidacion") in (1,5) ):
            attr[medida.get("codigoParametro")+"_value"] = medida.get("valor")
            attr[medida.get("codigoParametro")+"_unit"] = medida.get("unidade")
        if (medida.get("valor") == -9999 ):
            attr[medida.get("codigoParametro")+"_value"] = None
    return attr
