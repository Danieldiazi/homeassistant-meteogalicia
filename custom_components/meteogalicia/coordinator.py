"""Data update coordinators for MeteoGalicia integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import async_timeout

from homeassistant.core import HomeAssistant
try:
    from homeassistant.helpers.entity_platform import DEFAULT_SCAN_INTERVAL
except ImportError:  # pragma: no cover - fallback for newer/older HA
    try:
        from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
    except ImportError:  # pragma: no cover - last resort
        DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

_LOGGER = logging.getLogger(__name__)


def _get_scan_interval(config_scan_interval) -> timedelta:
    return config_scan_interval or DEFAULT_SCAN_INTERVAL


def _get_forecast_data_from_api(idc):
    """Call meteogalicia api in order to get forecast data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia()
    return meteogalicia_api.get_forecast_data(idc)


def _get_observation_data_from_api(idc):
    """Call meteogalicia api in order to get observation data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia()
    return meteogalicia_api.get_observation_data(idc)


def _get_observation_dailydata_by_station_from_api(ids):
    """Call meteogalicia api in order to get daily station data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia()
    return meteogalicia_api.get_observation_dailydata_by_station(ids)


def _get_observation_last10mindata_by_station_from_api(ids):
    """Call meteogalicia api in order to get last 10 min station data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia()
    return meteogalicia_api.get_observation_last10mindata_by_station(ids)


class MeteoGaliciaForecastCoordinator(DataUpdateCoordinator):
    """Coordinator for forecast data."""

    def __init__(self, hass: HomeAssistant, id_concello: str, scan_interval) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{const.DOMAIN}_forecast_{id_concello}",
            update_interval=_get_scan_interval(scan_interval),
        )
        self.id = id_concello

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(const.TIMEOUT):
                data = await self.hass.async_add_executor_job(
                    _get_forecast_data_from_api, self.id
                )
                if data is None:
                    _LOGGER.warning(
                        "[%s] Possible API connection problem. Currently unable to download forecast data from MeteoGalicia",
                        self.id,
                    )
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching forecast data for {self.id}: {err}"
            ) from err


class MeteoGaliciaObservationCoordinator(DataUpdateCoordinator):
    """Coordinator for observation data."""

    def __init__(self, hass: HomeAssistant, id_concello: str, scan_interval) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{const.DOMAIN}_observation_{id_concello}",
            update_interval=_get_scan_interval(scan_interval),
        )
        self.id = id_concello

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(const.TIMEOUT):
                data = await self.hass.async_add_executor_job(
                    _get_observation_data_from_api, self.id
                )
                if data is None:
                    _LOGGER.warning(
                        "[%s] Possible API connection problem. Currently unable to download observation data from MeteoGalicia",
                        self.id,
                    )
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching observation data for {self.id}: {err}"
            ) from err


class MeteoGaliciaStationDailyCoordinator(DataUpdateCoordinator):
    """Coordinator for station daily data."""

    def __init__(self, hass: HomeAssistant, id_estacion: str, scan_interval) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{const.DOMAIN}_station_daily_{id_estacion}",
            update_interval=_get_scan_interval(scan_interval),
        )
        self.id = id_estacion

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(const.TIMEOUT):
                data = await self.hass.async_add_executor_job(
                    _get_observation_dailydata_by_station_from_api, self.id
                )
                if data is None:
                    _LOGGER.warning(
                        "[%s] Possible API connection problem. Currently unable to download daily station data from MeteoGalicia",
                        self.id,
                    )
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching daily station data for {self.id}: {err}"
            ) from err


class MeteoGaliciaStationLast10MinCoordinator(DataUpdateCoordinator):
    """Coordinator for station last 10 min data."""

    def __init__(self, hass: HomeAssistant, id_estacion: str, scan_interval) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{const.DOMAIN}_station_last10min_{id_estacion}",
            update_interval=_get_scan_interval(scan_interval),
        )
        self.id = id_estacion

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(const.TIMEOUT):
                data = await self.hass.async_add_executor_job(
                    _get_observation_last10mindata_by_station_from_api, self.id
                )
                if data is None:
                    _LOGGER.warning(
                        "[%s] Possible API connection problem. Currently unable to download last 10 min station data from MeteoGalicia",
                        self.id,
                    )
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching last 10 min station data for {self.id}: {err}"
            ) from err
