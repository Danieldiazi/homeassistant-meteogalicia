"""The Sensor module for MeteoGalicia integration."""
from dataclasses import dataclass
import dataclasses
import sys
import logging
import async_timeout
import voluptuous as vol
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import __version__
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.entity import Entity
from . import const
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from meteogalicia_api.interface import MeteoGalicia

_LOGGER = logging.getLogger(__name__)

# Obtaining config from configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(const.CONF_ID_CONCELLO): cv.string}
)

# URL for Meteo Galicia webservice
URL = const.URL_FORECAST_CONCELLO


async def async_setup_platform(
    hass, config, add_entities, discovery_info=None
):  # pylint: disable=missing-docstring, unused-argument
    """Run async_setup_platform"""
    id_concello = config[const.CONF_ID_CONCELLO]

    # id_concello must to have 5 chars and be a number
    if len(id_concello) != 5 or (not id_concello.isnumeric()):
        _LOGGER.critical(
            "Configured (YAML) 'id_concello' '%s' is not valid", id_concello
        )
        return False

    session = async_create_clientsession(hass)

    try:
        async with async_timeout.timeout(30):
            response = await get_forecast_data(hass, id_concello)
            name = response["predConcello"].get("nome")
    except Exception as exception:
        _LOGGER.warning("[%s] %s", sys.exc_info()[0].__name__, exception)
        raise PlatformNotReady

    #   add_entities([MeteoGaliciaSensor(name, id_concello, session)], True)
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


# Sensor Class
class MeteoGaliciaForecastTemperatureMaxByDaySensor(
    Entity
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

    """Run async update."""

    async def async_update(self):
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(30):
                response = await get_forecast_data(self.hass, self.id)
                if response is None:
                    self._state = "unavailable"
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
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self):
        """Return the name."""
        return f"{const.INTEGRATION_NAME} -  {self._name} - {self.forecast_name} - {const.FORECAST_MAX_TEMPERATURE}"

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_MAX_TEMPERATURE.lower()}_{self.id}".replace(
            ",", ""
        )

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement."""
        return "°C"

    @property
    def icon(self):
        """Return icon."""
        return "mdi:thermometer"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr


class MeteoGaliciaForecastRainByDaySensor(Entity):  # pylint: disable=missing-docstring
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

    """Run async update."""

    async def async_update(self):
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(30):

                response = await get_forecast_data(self.hass, self.id)
                if response is None:
                    self._state = "unavailable"
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
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self):
        """Return the name."""
        return f"{const.INTEGRATION_NAME} -  {self._name} - {self.forecast_name} - {const.FORECAST_RAIN_PROBABILITY}"

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"{const.INTEGRATION_NAME.lower()}_{self._name}_{self.forecast_name.lower()}_{const.FORECAST_RAIN_PROBABILITY.lower()}_{self.id}".replace(
            ",", ""
        )

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement."""
        return "%"

    @property
    def icon(self):
        """Return icon."""
        return "mdi:percent"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr


# Sensor Class
"""Sensor class."""


class MeteoGaliciaTemperatureSensor(Entity):  # pylint: disable=missing-docstring
    def __init__(self, name, idc, session, hass):
        self._name = name
        self.id = idc
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}
        self.hass = hass

    """Run async update."""

    async def async_update(self):
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(30):

                response = await get_observation_data(self.hass, self.id)

                if response is None:
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia",
                        self.id,
                    )
                else:

                    _LOGGER.info(
                        "Test '%s' : '%s'",
                        self.id,
                        response.get("listaObservacionConcellos"),
                    )
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
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Couldn't update sensor (%s)",
                        self.id,
                        self.exception,
                    )

            elif not self.connected:
                if connected:
                    _LOGGER.info("[%s] Update of sensor completed", self.id)
                else:
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Still no update available (%s)", self.id, self.exception
                    )

            self.connected = connected

    @property
    def name(self):
        """Return the name."""
        return f"{const.INTEGRATION_NAME} - {self._name} - Temperature"

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"meteogalicia_{self._name.lower()}_temperature_{self.id}".replace(
            ",", ""
        )

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement."""
        return "°C"

    @property
    def icon(self):
        """Return icon."""
        return "mdi:thermometer"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self._attr
