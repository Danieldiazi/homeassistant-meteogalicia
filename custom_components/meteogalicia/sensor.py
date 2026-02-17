# -*- coding: utf-8 -*-
"""Módulo de sensores para la integración MeteoGalicia."""
import logging
import voluptuous as vol
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from . import const
from .util import safe_close_coordinators
from .coordinator import (
    MeteoGaliciaForecastCoordinator,
    MeteoGaliciaObservationCoordinator,
    MeteoGaliciaStationDailyCoordinator,
    MeteoGaliciaStationLast10MinCoordinator,
)

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by MeteoGalicia"

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
        return {
            **base_attr,
            const.ATTR_CONNECTED_AT: _get_coordinator_connected_at(self.coordinator),
            const.ATTR_API_LATENCY_MS: _get_coordinator_api_latency_ms(self.coordinator),
        }


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


# Obtaining config from configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    { vol.Optional(const.CONF_ID_CONCELLO): cv.string,
      vol.Optional(const.CONF_ID_ESTACION): cv.string,
      vol.Optional(const.CONF_ID_ESTACION_MEDIDA_DAILY): cv.string,
      vol.Optional(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN): cv.string,}
    
)

def _merge_entry_data(entry):
    """Mezcla datos y opciones de la entrada, permitiendo vaciar valores."""
    data = dict(entry.data)
    for key, value in entry.options.items():
        if value in ("", None):
            data.pop(key, None)
        else:
            data[key] = value
    return data


def _validate_id(value: str, expected_len: int, label: str) -> bool:
    """Valida que el id tenga longitud y sea numérico."""
    return isinstance(value, str) and len(value) == expected_len and value.isnumeric()


async def async_setup_platform(
    hass, config, add_entities, discovery_info=None
):  # pylint: disable=missing-docstring, unused-argument
    """Configura la plataforma de sensores definida en YAML."""
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    coordinators = (
        hass.data.setdefault(const.DOMAIN, {}).setdefault("yaml_coordinators", [])
    )
    if not hass.data[const.DOMAIN].get("yaml_close_registered"):
        hass.data[const.DOMAIN]["yaml_close_registered"] = True

        async def _close_yaml_coordinators(event):
            coordinators = hass.data.get(const.DOMAIN, {}).get(
                "yaml_coordinators", []
            )
            await safe_close_coordinators(coordinators)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _close_yaml_coordinators
        )

    if config.get(const.CONF_ID_CONCELLO, ""):
        id_concello = config[const.CONF_ID_CONCELLO]
        await setup_id_concello_platform(
            id_concello, add_entities, hass, scan_interval, coordinators
        )

    elif config.get(const.CONF_ID_ESTACION, ""):
        id_estacion = config[const.CONF_ID_ESTACION]
        await setup_id_estacion_platform(
            id_estacion, config, add_entities, hass, scan_interval, coordinators
        )


async def async_setup_entry(hass, entry, add_entities):
    """Configura sensores de MeteoGalicia desde una entrada de configuración."""
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL)
    data = _merge_entry_data(entry)
    coordinators = (
        hass.data.setdefault(const.DOMAIN, {})
        .setdefault(entry.entry_id, {})
        .setdefault("coordinators", [])
    )

    if data.get(const.CONF_ID_CONCELLO, ""):
        id_concello = data[const.CONF_ID_CONCELLO]
        await setup_id_concello_platform(
            id_concello, add_entities, hass, scan_interval, coordinators
        )
    elif data.get(const.CONF_ID_ESTACION, ""):
        id_estacion = data[const.CONF_ID_ESTACION]
        await setup_id_estacion_platform(
            id_estacion, data, add_entities, hass, scan_interval, coordinators
        )
        
        
async def setup_id_estacion_platform(
    id_estacion, config, add_entities, hass, scan_interval, coordinators=None
):
    """Configura la plataforma de estación y añade los sensores correspondientes."""
    daily_coordinator = None
    last10min_coordinator = None
    if config.get(const.CONF_ID_ESTACION_MEDIDA_DAILY, ""):
         id_measure_daily = config[const.CONF_ID_ESTACION_MEDIDA_DAILY]
    else:
        id_measure_daily = None
    
    if config.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN, ""):
        id_measure_last10min = config[const.CONF_ID_ESTACION_MEDIDA_LAST10MIN]  
    else:
        id_measure_last10min = None
    
    if not _validate_id(id_estacion, 5, "id_estacion"):
        _LOGGER.debug(
            "%s Configurado (YAML) 'id_estacion' '%s' no es válido",
            const.LOG_PREFIX,
            id_estacion,
        )
        return False
    else:
        entities = []

        if (
            (id_measure_daily is None and id_measure_last10min is None)
            or id_measure_daily is not None
        ):
            daily_coordinator = MeteoGaliciaStationDailyCoordinator(
                hass, id_estacion, scan_interval
            )
            if coordinators is not None:
                coordinators.append(daily_coordinator)
            await daily_coordinator.async_refresh()
            entities.append(
                MeteoGaliciaDailyDataByStationSensor(
                    id_estacion, id_estacion, id_measure_daily, daily_coordinator
                )
            )
            _LOGGER.info(
                "%s Añadidos datos diarios para '%s' con id '%s' - medida principal: %s",
                const.LOG_PREFIX,
                id_estacion,
                id_estacion,
                id_measure_daily,
            )

        if (
            (id_measure_daily is None and id_measure_last10min is None)
            or id_measure_last10min is not None
        ):
            last10min_coordinator = MeteoGaliciaStationLast10MinCoordinator(
                hass, id_estacion, scan_interval
            )
            if coordinators is not None:
                coordinators.append(last10min_coordinator)
            await last10min_coordinator.async_refresh()
            entities.append(
                MeteoGaliciaLast10MinDataByStationSensor(
                    id_estacion, id_estacion, id_measure_last10min, last10min_coordinator
                )
            )
            _LOGGER.info(
                "%s Añadidos datos de los últimos 10 min para '%s' con id '%s' - medida principal: %s",
                const.LOG_PREFIX,
                id_estacion,
                id_estacion,
                id_measure_last10min,
            )

        if entities:
            add_entities(entities)
            if daily_coordinator is not None:
                daily_coordinator.async_set_updated_data(daily_coordinator.data)
            if last10min_coordinator is not None:
                last10min_coordinator.async_set_updated_data(last10min_coordinator.data)


async def setup_id_concello_platform(
    id_concello, add_entities, hass, scan_interval, coordinators=None
):
        """Configura la plataforma de concello y añade los sensores correspondientes."""
        # id_concello must to have 5 chars and be a number
        if not _validate_id(id_concello, 5, "id_concello"):
            _LOGGER.critical(
            "%s Configurado (YAML) 'id_concello' '%s' no es válido", const.LOG_PREFIX, id_concello
            )
            return False
        else:
            forecast_coordinator = MeteoGaliciaForecastCoordinator(
                hass, id_concello, scan_interval
            )
            if coordinators is not None:
                coordinators.append(forecast_coordinator)
            await forecast_coordinator.async_refresh()
            if (
                not forecast_coordinator.last_update_success
                or not forecast_coordinator.data
                or not forecast_coordinator.data.get("predConcello")
            ):
                raise PlatformNotReady

            name = forecast_coordinator.data["predConcello"].get("nome")
            if not name:
                raise PlatformNotReady

            observation_coordinator = MeteoGaliciaObservationCoordinator(
                hass, id_concello, scan_interval
            )
            if coordinators is not None:
                coordinators.append(observation_coordinator)
            await observation_coordinator.async_refresh()
            
            forecast_temperature_by_day_sensor_config= [
                ("Today", 0, "tMax"),
                ("Today", 0, "tMin"),
                ("Tomorrow", 1, "tMax"),
                ("Tomorrow", 1,"tMin")]
            
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
                _LOGGER.info("%s Añadido sensor de temperatura %s %s para '%s' con id '%s'", const.LOG_PREFIX, item_sensor_config[0],item_sensor_config[2],name, id_concello)


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

            entities.append(
                MeteoGaliciaTemperatureSensor(
                    name, id_concello, observation_coordinator
                )
            )
            _LOGGER.info(
                "%s Añadido sensor de temperatura para '%s' con id '%s'", const.LOG_PREFIX, name, id_concello
            )
            add_entities(entities)
            forecast_coordinator.async_set_updated_data(forecast_coordinator.data)
            observation_coordinator.async_set_updated_data(observation_coordinator.data)


# Sensor Class
class MeteoGaliciaForecastTemperatureByDaySensor(
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
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

        item = data.get("predConcello")["listaPredDiaConcello"][self.forecast_day]
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
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
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

        item = data.get("predConcello")["listaPredDiaConcello"][self.forecast_day]
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
        hour = int(dt.now().strftime("%H"))
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




# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaDailyDataByStationSensor(
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor de datos diarios por estacion."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, name, ids, id_measure, coordinator):
        super().__init__(coordinator)
        self._name = name
        self.id = ids
        self.id_measure = id_measure
        self._state = None
        self._attr = {}
        if id_measure is None:
            self.name_suffix = ""
        else:
            self.name_suffix = "_" + id_measure

        # Valor por defecto para mantener la unidad disponible en fallos.
        self.measure_unit = None

    def _update_from_data(self, data) -> None:
        if not self.coordinator.last_update_success:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            return

        item = _get_first_list_item(data, "listDatosDiarios")
        if item is None:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            _LOGGER.warning(
                "No se pueden descargar los datos solicitados de MeteoGalicia: el id de estación %s no existe o hay un posible problema de conexión.",
                self.id,
            )
            return

        station = _get_first_list_item(item, "listaEstacions")
        if station is None:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            return

        self._attr = {
            **_base_attrs(self.id),
            "data": item.get("data"),
            "concello": station.get("concello"),
            "estacion": station.get("estacion"),
        }
        self._name = station.get("estacion")
        lista_medidas = station.get("listaMedidas")
        _apply_station_measures(self, lista_medidas)

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Devuelve el nombre."""
        return f"{self._name} - {self.name_suffix} - Station Daily Data" 

    @property
    def unique_id(self) -> str:
        """Devuelve un ID único para este sensor."""
        return f"meteogalicia_{self.id}_station_daily_data_{self.name_suffix.lower()}_{self.id}".replace(
            ",", ""
        )

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


# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaLast10MinDataByStationSensor(
    MeteoGaliciaExtraAttrsMixin, CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor de datos de los últimos 10 minutos por estación."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, name, ids, id_measure, coordinator):
        super().__init__(coordinator)
        self._name = name
        self.id = ids
        self.id_measure = id_measure
        self._state = None
        self._attr = {}
        if id_measure is None:
            self.name_suffix = ""
        else:
            self.name_suffix = "_" + id_measure

        # Valor por defecto para mantener la unidad disponible en fallos.
        self.measure_unit = None

    def _update_from_data(self, data) -> None:
        if not self.coordinator.last_update_success:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            return

        item = _get_first_list_item(data, "listUltimos10min")
        if item is None:
            self._state = None
            self.measure_unit = None
            self._attr = {}
            _LOGGER.warning(
                "No se pueden descargar los datos solicitados de MeteoGalicia: el id de estación %s no existe o hay un posible problema de conexión.",
                self.id,
            )
            return

        self._attr = {
            **_base_attrs(self.id),
            "instanteLecturaUTC": item.get("instanteLecturaUTC"),
            "idEstacion": item.get("idEstacion"),
            "estacion": item.get("estacion"),
        }

        self._name = item.get("estacion")
        lista_medidas = item.get("listaMedidas")
        _apply_station_measures(self, lista_medidas)

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Devuelve el nombre."""
        return f"{self._name} - {self.name_suffix} - Station Last 10 min Data" 

    @property
    def unique_id(self) -> str:
        """Devuelve un ID único para este sensor."""
        return f"meteogalicia_{self.id}_station_last_10_min_data_{self.name_suffix.lower()}_{self.id}".replace(
            ",", ""
        )

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
