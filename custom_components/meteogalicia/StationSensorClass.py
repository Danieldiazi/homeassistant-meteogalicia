import sys
import logging
import async_timeout
import voluptuous as vol
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import __version__, TEMP_CELSIUS, PERCENTAGE
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from . import const
from . import utils
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)

from meteogalicia_api.interface import MeteoGalicia


_LOGGER = logging.getLogger(__name__)



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




# Sensor Classget_observation_dailydata_by_station
class MeteoGaliciaDailyDataByStationSensor(SensorEntity):  # pylint: disable=missing-docstring
    """Sensor class."""

    
    def __init__(self, name, ids, id_measure,session, hass, attribution):
        self._name = name
        self.id = ids
        self.id_measure = id_measure
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass
        if (id_measure is None):
            self.name_suffix = ""
        else:
            self.name_suffix = "_"+id_measure
        
        #Set default value for measure_unit, because when a Timeout error appears sensor doesn't will create if "measure_unit" doesn't exists
        self.measure_unit = None
        _attr_attribution = attribution


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
                        "Currently unable to download asked data from MeteoGalicia: Or station id:%s doesn't exists or there are a possible API connection problem. ",
                        self.id,
                    )
                    self.measure_unit = None
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
                        lista_medidas = item.get("listaEstacions")[0].get("listaMedidas")
                        
                        self._attr = add_attributes_from_measures(lista_medidas, self._attr)
                        self._state = get_state_station_sensor(self.id_measure, self._attr, self.id)
                        self.measure_unit = get_measure_unit_station_sensor(self.id_measure, self._attr, self.id)
                        
                        
        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            _LOGGER.warning(
                        const.STRING_NOT_UPDATE_SENSOR,
                        self.id,
                        self.exception,sys.exc_info()
                    )
            connected = False
        else:
            connected = True
        finally:
            self._state = utils.check_connection(self.connected, connected, self._state, self.id, self.exception, _LOGGER)
            self.connected = connected

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
class MeteoGaliciaLast10MinDataByStationSensor(SensorEntity):  # pylint: disable=missing-docstring
    """Sensor class."""

    
    def __init__(self, name, ids, id_measure,session, hass, attribution):
        self._name = name
        self.id = ids
        self.id_measure = id_measure
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass
        if (id_measure is None):
            self.name_suffix = ""
        else:
            self.name_suffix = "_"+id_measure
        
        #Set default value for measure_unit, because when a Timeout error appears sensor doesn't will create if "measure_unit" doesn't exists
        self.measure_unit = None

        _attr_attribution = attribution


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
                        "Currently unable to download asked data from MeteoGalicia: Or station id:%s doesn't exists or there are a possible API connection problem. ",
                        self.id,
                    )
                    self.measure_unit = None
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
                        lista_medidas = item.get("listaMedidas")
                        self._attr = add_attributes_from_measures(lista_medidas, self._attr)
                        self._state = get_state_station_sensor(self.id_measure, self._attr, self.id)
                        self.measure_unit = get_measure_unit_station_sensor(self.id_measure, self._attr, self.id)
                        

        except Exception:  # pylint: disable=broad-except
            self.exception = sys.exc_info()[0].__name__
            _LOGGER.warning(
                        const.STRING_NOT_UPDATE_SENSOR,
                        self.id,
                        self.exception,sys.exc_info()
                    )
            connected = False
        else:
            connected = True
        finally:
            self._state = utils.check_connection(self.connected, connected, self._state, self.id, self.exception, _LOGGER)
            self.connected = connected

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




def get_state_station_sensor(id_measure, attributes,id):
    state = None
    if (id_measure is None):
        state = "Available"
    else:
        if id_measure+"_value" in attributes:
            state = attributes[id_measure+"_value"]
        else: #Measure for this sensor is unavailable
            state = None
            _LOGGER.warning("Couldn't update sensor with measure %s, it's unavailable for station id: %s", id_measure,id)
    return state

def get_measure_unit_station_sensor(id_measure, attributes,id):
    measure_unit = None
    if (id_measure is None):
        measure_unit = None
    else:
        if id_measure+"_value" in attributes:
            measure_unit = attributes[id_measure+"_unit"]
        else: #Measure for this sensor is unavailable
            measure_unit = None
            _LOGGER.warning("Couldn't update sensor with measure %s, it's unavailable for station id: %s", id_measure,id)
    return measure_unit


def add_attributes_from_measures(lista_medidas, attributes):
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


