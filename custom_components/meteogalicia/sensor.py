"""The Sensor module for MeteoGalicia integration."""
import logging
import voluptuous as vol
from homeassistant.const import CONF_SCAN_INTERVAL, PERCENTAGE, UnitOfTemperature
from homeassistant.exceptions import PlatformNotReady
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
from .coordinator import (
    MeteoGaliciaForecastCoordinator,
    MeteoGaliciaObservationCoordinator,
    MeteoGaliciaStationDailyCoordinator,
    MeteoGaliciaStationLast10MinCoordinator,
)

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by MeteoGalicia"

# Obtaining config from configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    { vol.Optional(const.CONF_ID_CONCELLO): cv.string,
      vol.Optional(const.CONF_ID_ESTACION): cv.string,
      vol.Optional(const.CONF_ID_ESTACION_MEDIDA_DAILY): cv.string,
      vol.Optional(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN): cv.string,}
    
)


async def async_setup_platform(
    hass, config, add_entities, discovery_info=None
):  # pylint: disable=missing-docstring, unused-argument
    """Run async_setup_platform"""
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    if config.get(const.CONF_ID_CONCELLO, ""):
        id_concello = config[const.CONF_ID_CONCELLO]
        await setup_id_concello_platform(
            id_concello, add_entities, hass, scan_interval
        )

    elif config.get(const.CONF_ID_ESTACION, ""):
        id_estacion = config[const.CONF_ID_ESTACION]
        await setup_id_estacion_platform(
            id_estacion, config, add_entities, hass, scan_interval
        )


async def async_setup_entry(hass, entry, add_entities):
    """Set up MeteoGalicia sensors from a config entry."""
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL)
    data = dict(entry.data)

    if data.get(const.CONF_ID_CONCELLO, ""):
        id_concello = data[const.CONF_ID_CONCELLO]
        await setup_id_concello_platform(
            id_concello, add_entities, hass, scan_interval
        )
    elif data.get(const.CONF_ID_ESTACION, ""):
        id_estacion = data[const.CONF_ID_ESTACION]
        await setup_id_estacion_platform(
            id_estacion, data, add_entities, hass, scan_interval
        )
        
        
async def setup_id_estacion_platform(
    id_estacion, config, add_entities, hass, scan_interval
):
    """ setup station platform, adding their sensors based on configuration"""
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
    
    if len(id_estacion) != 5 or (not id_estacion.isnumeric()):
        _LOGGER.debug(
            "Configured (YAML) 'id_estacion' '%s' is not valid", id_estacion
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
            await daily_coordinator.async_refresh()
            entities.append(
                MeteoGaliciaDailyDataByStationSensor(
                    id_estacion, id_estacion, id_measure_daily, daily_coordinator
                )
            )
            _LOGGER.info(
                "Added daily data for '%s' with id '%s' - main measure is: %s",
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
            await last10min_coordinator.async_refresh()
            entities.append(
                MeteoGaliciaLast10MinDataByStationSensor(
                    id_estacion, id_estacion, id_measure_last10min, last10min_coordinator
                )
            )
            _LOGGER.info(
                "Added last 10 min data for '%s' with id '%s' - main measure is: %s",
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
    id_concello, add_entities, hass, scan_interval
):
        """ setup concello platform, adding their sensors based on configuration"""
        # id_concello must to have 5 chars and be a number
        if len(id_concello) != 5 or (not id_concello.isnumeric()):
            _LOGGER.critical(
            "Configured (YAML) 'id_concello' '%s' is not valid", id_concello
            )
            return False
        else:
            forecast_coordinator = MeteoGaliciaForecastCoordinator(
                hass, id_concello, scan_interval
            )
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
                _LOGGER.info("Added %s %s temp forecast sensor for '%s' with id '%s'", item_sensor_config[0],item_sensor_config[2],name, id_concello)


            entities.append(
                MeteoGaliciaForecastRainByDaySensor(
                    name, id_concello, "Today", 0, False, forecast_coordinator
                )
            )
            _LOGGER.info(
                "Added today forecast rain probability sensor for '%s' with id '%s'",
                name,
                id_concello,
            )
            entities.append(
                MeteoGaliciaForecastRainByDaySensor(
                    name, id_concello, "Tomorrow", 1, True, forecast_coordinator
                )
            )
            _LOGGER.info(
                "Added tomorrow forecast rain probability sensor for '%s' with id '%s'",
                name,
                id_concello,
            )

            entities.append(
                MeteoGaliciaTemperatureSensor(
                    name, id_concello, observation_coordinator
                )
            )
            _LOGGER.info(
                "Added weather temperature sensor for '%s' with id '%s'", name, id_concello
            )
            add_entities(entities)
            forecast_coordinator.async_set_updated_data(forecast_coordinator.data)
            observation_coordinator.async_set_updated_data(observation_coordinator.data)


# Sensor Class
class MeteoGaliciaForecastTemperatureByDaySensor(
    CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor class."""

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
            self.forecast_field_name = f"{self.forecast_field} not defined"

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
            "information": [],
            "integration": "meteogalicia",
            "forecast_date": item.get("dataPredicion"),
            "id": self.id,
        }

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} - {self.forecast_field_name} - {self.forecast_name} "

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""

        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{self.forecast_field_name.lower()}_{self.id}".replace(
            ",", ""
        )

    @property
    def icon(self):
        """Return icon."""
        return "mdi:thermometer"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr

    @property
    def device_class(self) -> str:
        """Return attributes."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement."""
        return UnitOfTemperature.CELSIUS


class MeteoGaliciaForecastRainByDaySensor(
    CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """ Forecast rain by day sensor"""
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
            "information": [],
            "integration": "meteogalicia",
            "forecast_date": item.get("dataPredicion"),
            "rain_probability_noon": pchoiva.get("manha"),
            "rain_probability_afternoon": pchoiva.get("tarde"),
            "rain_probability_night": pchoiva.get("noite"),
            "id": self.id,
        }

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} - {const.FORECAST_RAIN_PROBABILITY} - {self.forecast_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        unique_id = f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_RAIN_PROBABILITY.lower()}_{self.id}"
        unique_id = unique_id.replace(",", "")
        return unique_id

    @property
    def icon(self):
        """Return icon."""
        return "mdi:percent"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement."""
        return PERCENTAGE


# Sensor Class
class MeteoGaliciaTemperatureSensor(
    CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor class."""

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
            "information": [],
            "integration": "meteogalicia",
            "local_date": item.get("dataLocal"),
            "utc_date": item.get("dataUTC"),
            "temperature_feeling": item.get("sensacionTermica"),
            "reference": item.get("nomeConcello"),
            "id": self.id,
        }

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} - Temperature"

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"meteogalicia_{self._name.lower()}_temperature_{self.id}".replace(
            ",", ""
        )

    @property
    def icon(self):
        """Return icon."""
        return "mdi:thermometer"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self) -> str:
        """Return attributes."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement."""
        return UnitOfTemperature.CELSIUS








def get_state_forecast_rain_by_day_sensor(max_value, item):
    """ obtain the correct state value"""
    pchoiva = item.get("pchoiva")
    if not isinstance(pchoiva, dict):
        return None

    if max_value:
        # If max_value is true: state will be the highest value
        values = [pchoiva.get("manha"), pchoiva.get("tarde"), pchoiva.get("noite")]
        values = [value for value in values if value is not None]
        if not values:
            return None
        state = max(values)
    else:
        # if max_value is false: state will be the time slot value corresponding to current time
        field = "manha"  # noon field: 6-14 h
        hour = int(dt.now().strftime("%H"))
        if hour >= 21:
            field = "noite"  # night field: 21-6 h
        elif hour >= 14:
            field = "tarde"  # afternoon field: 14-21 h
        elif hour < 6:
            field = "noite"  # night field: 21-6 h
        state = pchoiva.get(field)

    if state is not None and state < 0:
        # Sometimes, web service returns -9999 if data is not available at this moment.
        state = None
    return state




# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaDailyDataByStationSensor(
    CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor class."""

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

        # Set default value for measure_unit to keep it available on failures.
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
                "Currently unable to download asked data from MeteoGalicia: Or station id:%s doesn't exists or there are a possible API connection problem. ",
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
            "information": [],
            "integration": "meteogalicia",
            "data": item.get("data"),
            "concello": station.get("concello"),
            "estacion": station.get("estacion"),
            "id": self.id,
        }
        self._name = station.get("estacion")
        lista_medidas = station.get("listaMedidas")
        _apply_station_measures(self, lista_medidas)

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} - {self.name_suffix} - Station Daily Data" 

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"meteogalicia_{self.id}_station_daily_data_{self.name_suffix.lower()}_{self.id}".replace(
            ",", ""
        )

    @property
    def icon(self):
        """Return icon."""
        return "mdi:information"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

        
    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement."""
        return self.measure_unit


# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaLast10MinDataByStationSensor(
    CoordinatorEntity, SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor class."""

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

        # Set default value for measure_unit to keep it available on failures.
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
                "Currently unable to download asked data from MeteoGalicia: Or station id:%s doesn't exists or there are a possible API connection problem. ",
                self.id,
            )
            return

        self._attr = {
            "information": [],
            "integration": "meteogalicia",
            "instanteLecturaUTC": item.get("instanteLecturaUTC"),
            "idEstacion": item.get("idEstacion"),
            "estacion": item.get("estacion"),
            "id": self.id,
        }

        self._name = item.get("estacion")
        lista_medidas = item.get("listaMedidas")
        _apply_station_measures(self, lista_medidas)

    def _handle_coordinator_update(self) -> None:
        self._update_from_data(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} - {self.name_suffix} - Station Last 10 min Data" 

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"meteogalicia_{self.id}_station_last_10_min_data_{self.name_suffix.lower()}_{self.id}".replace(
            ",", ""
        )

    @property
    def icon(self):
        """Return icon."""
        return "mdi:information"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state        
    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement."""
        return self.measure_unit




def _get_first_list_item(container, list_key):
    """Return first item from a list in a dict or None if missing."""
    if not isinstance(container, dict):
        return None
    items = container.get(list_key)
    if not items:
        return None
    return items[0]


def _apply_station_measures(entity, lista_medidas):
    """Populate attributes, state, and unit from station measures."""
    if not lista_medidas:
        entity._state = None
        entity.measure_unit = None
        return
    entity._attr = add_attributes_from_measures(lista_medidas, entity._attr)
    entity._state = get_state_station_sensor(entity.id_measure, entity._attr, entity.id)
    entity.measure_unit = get_measure_unit_station_sensor(entity.id_measure, entity._attr, entity.id)




def get_state_station_sensor(id_measure, attributes,id_station):
    """ get the state value for a station sensor"""
    state = "Available"
    if (id_measure is not None):
        if id_measure+"_value" in attributes:
            state = attributes[id_measure+"_value"]
        else: #Measure for this sensor is unavailable
            state = None
            _LOGGER.warning(const.STRING_MEASURE_NOT_AVAILABLE, id_measure,id_station)
    return state

def get_measure_unit_station_sensor(id_measure, attributes,id_station):
    """ get the measure_unit value for a station sensor"""
    measure_unit = None
    if (id_measure is not None):
        if id_measure+"_value" in attributes:
            measure_unit = attributes[id_measure+"_unit"]
        else: #Measure for this sensor is unavailable
            measure_unit = None
            _LOGGER.warning(const.STRING_MEASURE_NOT_AVAILABLE, id_measure,id_station)
    return measure_unit


def add_attributes_from_measures(lista_medidas, attributes):
    """ Add attributes from measures received for station sensor"""
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
