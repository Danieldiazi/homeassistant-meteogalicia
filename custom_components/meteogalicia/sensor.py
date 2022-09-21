import sys
import logging
import async_timeout
from enum import Enum
import voluptuous as vol
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import __version__
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.entity import Entity

from . import const

import homeassistant.helpers.config_validation as cv

__version__ = "0.1"

CONF_ID_CONCELLO = "id_concello"

_LOGGER = logging.getLogger(__name__)

# Obtain config from configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_ID_CONCELLO): cv.string})

# URL for Meteo Galicia webservice
URL = const.URL_FORECAST_CONCELLO


HEADERS = {
    "accept": "application/ld+json",
    "user-agent": f"HomeAssistant/{__version__}",
}

"""Run async_setup_platform"""


async def async_setup_platform(
    hass, config, add_entities, discovery_info=None
):  # pylint: disable=missing-docstring, unused-argument

    id_concello = config[CONF_ID_CONCELLO]

    # id_concello must to have 5 chars and be a number
    if len(id_concello) != 5 or (not id_concello.isnumeric()):
        _LOGGER.critical(
            "Configured (YAML) 'id_concello' '%s' is not valid", id_concello
        )
        return False

    session = async_create_clientsession(hass)

    try:
        async with async_timeout.timeout(20):
            response = await session.get(URL.format(id_concello))
            data = await response.json()
            name = data["predConcello"].get("nome")
    except Exception as exception:
        _LOGGER.warning("[%s] %s", sys.exc_info()[0].__name__, exception)
        raise PlatformNotReady

    #   add_entities([MeteoGaliciaSensor(name, id_concello, session)], True)
    add_entities(
        [
            MeteoGaliciaForecastTemperatureMaxByDaySensor(
                name, id_concello, "Today", 0, session
            )
        ],
        True,
    )
    _LOGGER.info("Added today forecast sensor for '%s' with id '%s'", name, id_concello)
    add_entities(
        [
            MeteoGaliciaForecastTemperatureMaxByDaySensor(
                name, id_concello, "Tomorrow", 1, session
            )
        ],
        True,
    )

    add_entities(
        [MeteoGaliciaTemperatureSensor(name, id_concello, session)],
        True,
    )
    _LOGGER.info(
        "Added tomorrow forecast sensor for '%s' with id '%s'", name, id_concello
    )


# Sensor Class
"""Sensor class."""


class MeteoGaliciaForecastTemperatureMaxByDaySensor(
    Entity
):  # pylint: disable=missing-docstring
    def __init__(self, name, id, forecast_name, forecast_day, session):
        self._name = name
        self.id = id
        self.forecast_name = forecast_name
        self.forecast_day = forecast_day
        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}

    """Run async update."""

    async def async_update(self):
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(10):
                response = await self.session.get(URL.format(self.id))
                if response.status != 200:
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia - HTTP status code %s",
                        self.id,
                        response.status,
                    )
                else:
                    data = await response.json()
                    # _LOGGER.info("Test '%s' : '%s'",   self.id, data.get("predConcello")["listaPredDiaConcello"],     )
                    if data.get("predConcello") is not None:
                        item = data.get("predConcello")["listaPredDiaConcello"][
                            self.forecast_day
                        ]

                        self._state = item.get("tMax", "null")

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


# Sensor Class
"""Sensor class."""


class MeteoGaliciaTemperatureSensor(Entity):  # pylint: disable=missing-docstring
    def __init__(self, name, id, session):
        self._name = name
        self.id = id

        self.session = session
        self._state = 0
        self.connected = True
        self.exception = None
        self._attr = {}

    """Run async update."""

    async def async_update(self):
        """Run async update ."""
        information = []
        connected = False
        try:
            async with async_timeout.timeout(10):
                response = await self.session.get(
                    const.URL_OBS_CONCELLO.format(self.id)
                )
                if response.status != 200:
                    self._state = "unavailable"
                    _LOGGER.warning(
                        "[%s] Possible API  connection  problem. Currently unable to download data from MeteoGalicia - HTTP status code %s",
                        self.id,
                        response.status,
                    )
                else:
                    data = await response.json()
                    # _LOGGER.info("Test '%s' : '%s'",   self.id, data.get("predConcello")["listaPredDiaConcello"],     )
                    if data.get("listaObservacionConcellos") is not None:
                        item = data.get("listaObservacionConcellos")[0]

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
