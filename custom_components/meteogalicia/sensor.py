"""The Sensor module for MeteoGalicia integration."""
import sys
import logging
import async_timeout
import voluptuous as vol
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import __version__, TEMP_CELSIUS, PERCENTAGE
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from . import const
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)


from meteogalicia_api.interface import MeteoGalicia

_LOGGER = logging.getLogger(__name__)

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
    
    

    session = async_create_clientsession(hass)
    if config.get(const.CONF_ID_CONCELLO, ""):
        id_concello = config[const.CONF_ID_CONCELLO]
        # id_concello must to have 5 chars and be a number
        if len(id_concello) != 5 or (not id_concello.isnumeric()):
            _LOGGER.critical(
            "Configured (YAML) 'id_concello' '%s' is not valid", id_concello
            )
            return False
        else:
            try:
                async with async_timeout.timeout(const.TIMEOUT):
                    response = await get_forecast_data(hass, id_concello)
                    name = response["predConcello"].get("nome")
            except Exception as exception:
                _LOGGER.warning("[%s] %s", sys.exc_info()[0].__name__, exception)
                raise PlatformNotReady

            add_entities(
            [
                MeteoGaliciaForecastTemperatureMaxByDaySensor(
                    name, id_concello, "Today", 0, session, hass
                )
            ],
            True,
                )
            _LOGGER.info("Added today forecast sensor for '%s' with id '%s'", name, id_concello)
            add_entities(
                [
                    MeteoGaliciaForecastTemperatureMaxByDaySensor(
                        name, id_concello, "Tomorrow", 1, session, hass
                    )
                ],
                True,
            )
            _LOGGER.info(
                "Added tomorrow forecast sensor for '%s' with id '%s'", name, id_concello
            )

            add_entities(
                [
                    MeteoGaliciaForecastTemperatureMinByDaySensor(
                        name, id_concello, "Today", 0, session, hass
                    )
                ],
                True,
            )
            _LOGGER.info(
                "Added min temperature today forecast sensor for '%s' with id '%s'",
                name,
                id_concello,
            )
            add_entities(
                [
                    MeteoGaliciaForecastTemperatureMinByDaySensor(
                        name, id_concello, "Tomorrow", 1, session, hass
                    )
                ],
                True,
            )
            _LOGGER.info(
                "Added min temperature tomorrow forecast sensor for '%s' with id '%s'",
                name,
                id_concello,
            )

            add_entities(
                [
                    MeteoGaliciaForecastRainByDaySensor(
                        name, id_concello, "Today", 0, False, session, hass
                    )
                ],
                True,
            )
            _LOGGER.info(
                "Added today forecast rain probability sensor for '%s' with id '%s'",
                name,
                id_concello,
            )
            add_entities(
                [
                    MeteoGaliciaForecastRainByDaySensor(
                        name, id_concello, "Tomorrow", 1, True, session, hass
                    )
                ],
                True,
            )
            _LOGGER.info(
                "Added tomorrow forecast rain probability sensor for '%s' with id '%s'",
                name,
                id_concello,
            )

            add_entities(
                [MeteoGaliciaTemperatureSensor(name, id_concello, session, hass)],
                True,
            )
            _LOGGER.info(
                "Added weather temperature sensor for '%s' with id '%s'", name, id_concello
            )


    elif config.get(const.CONF_ID_ESTACION, ""):
        id_estacion = config[const.CONF_ID_ESTACION]

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
                "Configured (YAML) 'id_estacion' '%s' is not valid", id_concello
            )
            return False
        else:
            
            if ((id_measure_daily is None and id_measure_last10min is None) or id_measure_daily is not None):
                add_entities(
                [MeteoGaliciaDailyDataByStationSensor(id_estacion, id_estacion, id_measure_daily,session, hass)],
                True,)
                _LOGGER.info(
                "Added daily data for '%s' with id '%s' - main measure is: %s", id_estacion, id_estacion, id_measure_daily)
            
            if ((id_measure_daily is None and id_measure_last10min is None) or id_measure_last10min is not None):
                add_entities(
                [MeteoGaliciaLast10MinDataByStationSensor(id_estacion, id_estacion, id_measure_last10min,session, hass)],
                True,)
                _LOGGER.info(
                "Added last 10 min data for '%s' with id '%s' - main measure is: %s", id_estacion, id_estacion, id_measure_last10min)




    





async def get_observation_data(hass, idc):
    """Poll weather data from MeteoGalicia API."""

    data = await hass.async_add_executor_job(_get_observation_data_from_api, idc)
    return data


def _get_observation_data_from_api(idc):
    """Call meteogalicia api in order to get obsertation data"""
    meteogalicia_api = MeteoGalicia()
    data = meteogalicia_api.get_observation_data(idc)
    return data


async def get_forecast_data(hass, idc):
    """Poll weather data from MeteoGalicia API."""

    data = await hass.async_add_executor_job(_get_forecast_data_from_api, idc)
    return data


def _get_forecast_data_from_api(idc):
    """Call meteogalicia api in order to get obsertation data"""
    meteogalicia_api = MeteoGalicia()
    data = meteogalicia_api.get_forecast_data(idc)
    return data



async def get_observation_dailydata_by_station(hass, ids):
    """Poll weather data from MeteoGalicia API."""

    data = await hass.async_add_executor_job(_get_observation_dailydata_by_station_from_api, ids)
    return data


def _get_observation_dailydata_by_station_from_api(ids):
    """Call meteogalicia api in order to get obsertation data"""
    meteogalicia_api = MeteoGalicia()
    data = meteogalicia_api.get_observation_dailydata_by_station(ids)
    return data


async def get_observation_last10mindata_by_station(hass, ids):
    """Poll weather data from MeteoGalicia API."""

    data = await hass.async_add_executor_job(_get_observation_last10mindata_by_station_from_api, ids)
    return data


def _get_observation_last10mindata_by_station_from_api(ids):
    """Call meteogalicia api in order to get obsertation data"""
    meteogalicia_api = MeteoGalicia()
    data = meteogalicia_api.get_observation_last10mindata_by_station(ids)
    return data

# Sensor Class
class MeteoGaliciaForecastTemperatureMaxByDaySensor(
    SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor class."""

    def __init__(self, name, idc, forecast_name, forecast_day, session, hass):
        self._name = name
        self.id = idc
        self.forecast_name = forecast_name
        self.forecast_day = forecast_day
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass

    async def async_update(self) -> None:
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(const.TIMEOUT):
                response = await get_forecast_data(self.hass, self.id)
                if response is None:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia - HTTP status code %s",
                        self.id,
                        response.status,
                    )
                else:

                    # _LOGGER.info("Test '%s' : '%s'",   self.id, data.get("predConcello")["listaPredDiaConcello"],     )
                    if response.get("predConcello") is not None:
                        item = response.get("predConcello")["listaPredDiaConcello"][
                            self.forecast_day
                        ]
                        state = item.get("tMax", "null")
                        if (
                            state < 0
                        ):  # Sometimes, web service returns -9999 if data is not available at this moment.
                            state = None

                        self._state = state

                        self._attr = {
                            "information": information,
                            "integration": "meteogalicia",
                            "forecast_date": item.get("dataPredicion"),
                            "id": self.id,
                        }

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            connected = False
        else:
            connected = True
        finally:
            # Handle connection messages here.
            if self.connected:
                if not connected:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{const.INTEGRATION_NAME} -  {self._name} - {self.forecast_name} - {const.FORECAST_MAX_TEMPERATURE}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_MAX_TEMPERATURE.lower()}_{self.id}".replace(
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
        return TEMP_CELSIUS


# Sensor Class
class MeteoGaliciaForecastTemperatureMinByDaySensor(
    SensorEntity
):  # pylint: disable=missing-docstring
    """Sensor class."""

    def __init__(self, name, idc, forecast_name, forecast_day, session, hass):
        self._name = name
        self.id = idc
        self.forecast_name = forecast_name
        self.forecast_day = forecast_day
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass

    async def async_update(self) -> None:
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(const.TIMEOUT):
                response = await get_forecast_data(self.hass, self.id)
                if response is None:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia - HTTP status code %s",
                        self.id,
                        response.status,
                    )
                else:

                    # _LOGGER.info("Test '%s' : '%s'",   self.id, data.get("predConcello")["listaPredDiaConcello"],     )
                    if response.get("predConcello") is not None:
                        item = response.get("predConcello")["listaPredDiaConcello"][
                            self.forecast_day
                        ]
                        state = item.get("tMin", "null")
                        if (
                            state < 0
                        ):  # Sometimes, web service returns -9999 if data is not available.
                            state = None

                        self._state = state

                        self._attr = {
                            "information": information,
                            "integration": "meteogalicia",
                            "forecast_date": item.get("dataPredicion"),
                            "id": self.id,
                        }

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            connected = False
        else:
            connected = True
        finally:
            # Handle connection messages here.
            if self.connected:
                if not connected:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{const.INTEGRATION_NAME} -  {self._name} - {self.forecast_name} - {const.FORECAST_MIN_TEMPERATURE}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_MIN_TEMPERATURE.lower()}_{self.id}".replace(
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
        return TEMP_CELSIUS


class MeteoGaliciaForecastRainByDaySensor(
    SensorEntity
):  # pylint: disable=missing-docstring
    def __init__(
        self, name, idc, forecast_name, forecast_day, max_value, session, hass
    ):
        self._name = name
        self.id = idc
        self.forecast_name = forecast_name
        self.forecast_day = forecast_day
        self.max_value = max_value
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass

    async def async_update(self) -> None:
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(const.TIMEOUT):

                response = await get_forecast_data(self.hass, self.id)
                if response is None:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia",
                        self.id,
                    )
                else:
                    if response.get("predConcello") is not None:
                        item = response.get("predConcello")["listaPredDiaConcello"][
                            self.forecast_day
                        ]

                        state = None
                        if self.max_value:
                            # If max_value is true: state will be the highest value
                            state = max(
                                item.get("pchoiva", "null")["manha"],
                                item.get("pchoiva", "null")["tarde"],
                                item.get("pchoiva", "null")["noite"],
                            )
                        else:
                            # if max_value is false: state will be the time slot value corresponding to current time
                            field = "manha"  # noon field: 6-14 h
                            hour = int(dt.now().strftime("%H"))
                            if hour > 21:
                                field = "noite"  # night field: 21-6 h
                            elif hour > 14:
                                field = "tarde"  # afternoon field: 14-21 h
                            elif hour < 6:
                                field = "noite"  # night field: 21-6 h
                            state = item.get("pchoiva", "null")[field]

                        if (
                            state < 0
                        ):  # Sometimes, web service returns -9999 if data is not available at this moment.
                            state = None

                        self._state = state

                        self._attr = {
                            "information": information,
                            "integration": "meteogalicia",
                            "forecast_date": item.get("dataPredicion"),
                            "rain_probability_noon": item.get("pchoiva", "null")[
                                "manha"
                            ],
                            "rain_probability_afternoon": item.get("pchoiva", "null")[
                                "tarde"
                            ],
                            "rain_probability_night": item.get("pchoiva", "null")[
                                "noite"
                            ],
                            "id": self.id,
                        }

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            connected = False
        else:
            connected = True
        finally:
            # Handle connection messages here.
            if self.connected:
                if not connected:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{const.INTEGRATION_NAME} -  {self._name} - {self.forecast_name} - {const.FORECAST_RAIN_PROBABILITY}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_RAIN_PROBABILITY.lower()}_{self.id}".replace(
            ",", ""
        )

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
class MeteoGaliciaTemperatureSensor(SensorEntity):  # pylint: disable=missing-docstring
    """Sensor class."""

    def __init__(self, name, idc, session, hass):
        self._name = name
        self.id = idc
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass

    async def async_update(self) -> None:
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(const.TIMEOUT):

                response = await get_observation_data(self.hass, self.id)

                if response is None:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia",
                        self.id,
                    )
                else:

                    if response.get("listaObservacionConcellos") is not None:
                        item = response.get("listaObservacionConcellos")[0]

                        self._state = item.get("temperatura", "null")

                        self._attr = {
                            "information": information,
                            "integration": "meteogalicia",
                            "local_date": item.get("dataLocal"),
                            "utc_date": item.get("dataUTC"),
                            "temperature_feeling": item.get("sensacionTermica"),
                            "reference": item.get("nomeConcello"),
                            "id": self.id,
                        }

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            connected = False
        else:
            connected = True
        finally:
            # Handle connection messages here.
            if self.connected:
                if not connected:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{const.INTEGRATION_NAME} - {self._name} - Temperature"

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
        return TEMP_CELSIUS




# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaDailyDataByStationSensor(SensorEntity):  # pylint: disable=missing-docstring
    """Sensor class."""

    def __init__(self, name, ids, idMeasure,session, hass):
        self._name = name
        self.id = ids
        self.idMeasure = idMeasure
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass
        if (idMeasure is None):
            self.nameSuffix = ""
        else:
            self.nameSuffix = "_"+idMeasure


    async def async_update(self) -> None:
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(const.TIMEOUT):

                response = await get_observation_dailydata_by_station(self.hass, self.id)

                if response is None or len(response.get("listDatosDiarios"))<=0:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Possible API connection problem. Currently unable to download data from MeteoGalicia. Maybe next time...",
                        self.id,
                    )
                else:
                   
                    if response.get("listDatosDiarios") is not None:
                        
                        item = response.get("listDatosDiarios")[0]


                        self._attr = {
                            "information": information,
                            "integration": "meteogalicia",
                            "data": item.get("data"),
                            #"utc_date": item.get("dataUTC"),
                            "concello": item.get("listaEstacions")[0].get("concello"),
                            "estacion": item.get("listaEstacions")[0].get("estacion"),
                            "id": self.id,
                            
                        }
                        self._name = item.get("listaEstacions")[0].get("estacion")
                        listaMedidas = item.get("listaEstacions")[0].get("listaMedidas")
                        
                        for medida in listaMedidas:
                             self._attr[medida.get("codigoParametro")+"_value"] = medida.get("valor")
                             self._attr[medida.get("codigoParametro")+"_unit"] = medida.get("unidade")
                        
                        
                        if (self.idMeasure is None):
                            self._state = "Available"
                        else:
                            self._state = self._attr[self.idMeasure+"_value"]

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s),%s",
                        self.id,
                        self.exception,sys.exc_info()
                    )
            connected = False
        else:
            connected = True
        finally:
            # Handle connection messages here.
            if self.connected:
                if not connected:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s),%s",
                        self.id,
                        self.exception,sys.exc_info()[0]
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self) -> str:
        """Return the name."""
        
        
        return f"{const.INTEGRATION_NAME} - {self._name} - Station Daily Data{self.nameSuffix}" 

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"meteogalicia_{self._name.lower()}_station_daily_data_{self.nameSuffix.lower()}_{self.id}".replace(
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

# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaLast10MinDataByStationSensor(SensorEntity):  # pylint: disable=missing-docstring
    """Sensor class."""

    def __init__(self, name, ids, idMeasure,session, hass):
        self._name = name
        self.id = ids
        self.idMeasure = idMeasure
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass
        if (idMeasure is None):
            self.nameSuffix = ""
        else:
            self.nameSuffix = "_"+idMeasure


    async def async_update(self) -> None:
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(const.TIMEOUT):

                response = await get_observation_last10mindata_by_station(self.hass, self.id)

                if response is None or len(response.get("listUltimos10min"))<=0:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Possible API connection problem. Currently unable to download data from MeteoGalicia. Maybe next time...",
                        self.id,
                    )
                else:
                   
                    if response.get("listUltimos10min") is not None:
                        
                        item = response.get("listUltimos10min")[0]

                        
                        self._attr = {
                            "information": information,
                            "integration": "meteogalicia",
                            "instanteLecturaUTC": item.get("instanteLecturaUTC"),
                            "idEstacion": item.get("idEstacion"),
                            "estacion": item.get("estacion"),
                            "id": self.id,
                            
                        }
                        
                        self._name = item.get("estacion")
                        listaMedidas = item.get("listaMedidas")
                        
                        for medida in listaMedidas:
                             self._attr[medida.get("codigoParametro")+"_value"] = medida.get("valor")
                             self._attr[medida.get("codigoParametro")+"_unit"] = medida.get("unidade")
                        
                        
                        if (self.idMeasure is None):
                            self._state = "Available"
                        else:
                            self._state = self._attr[self.idMeasure+"_value"]

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s),%s",
                        self.id,
                        self.exception,sys.exc_info()
                    )
            connected = False
        else:
            connected = True
        finally:
            # Handle connection messages here.
            if self.connected:
                if not connected:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s),%s",
                        self.id,
                        self.exception,sys.exc_info()[0]
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = None
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self) -> str:
        """Return the name."""
        
        
        return f"{const.INTEGRATION_NAME} - {self._name} - Station Last 10 min Data{self.nameSuffix}" 

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return f"meteogalicia_{self._name.lower()}_station_last_10_min_data_{self.nameSuffix.lower()}_{self.id}".replace(
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

