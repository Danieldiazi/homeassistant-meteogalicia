"""Data update coordinators for MeteoGalicia integration."""
from __future__ import annotations

from datetime import datetime
from datetime import timedelta
import asyncio
import logging
import time
import async_timeout
import requests

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
    if isinstance(config_scan_interval, (int, float)):
        return timedelta(seconds=config_scan_interval)
    return config_scan_interval or DEFAULT_SCAN_INTERVAL


async def _async_api_call_with_latency(coordinator, api_call, *args):
    """Call API function via executor and store call latency in milliseconds."""
    started = time.perf_counter()
    data = await coordinator.hass.async_add_executor_job(api_call, *args)
    coordinator.last_api_latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    if data is not None:
        coordinator.last_api_connected_at = datetime.utcnow().isoformat()
    return data


def _get_forecast_data_from_api(idc, session: requests.Session):
    """Call meteogalicia api in order to get forecast data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_forecast_data(idc)


def _get_observation_data_from_api(idc, session: requests.Session):
    """Call meteogalicia api in order to get observation data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_observation_data(idc)


def _get_observation_dailydata_by_station_from_api(ids, session: requests.Session):
    """Call meteogalicia api in order to get daily station data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_observation_dailydata_by_station(ids)


def _get_observation_last10mindata_by_station_from_api(ids, session: requests.Session):
    """Call meteogalicia api in order to get last 10 min station data."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
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
        self._had_data_error = False
        self.last_api_latency_ms = None
        self.last_api_connected_at = None
        self._session = requests.Session()
        self._session_lock = asyncio.Lock()

    async def _async_update_data(self):
        try:
            async with self._session_lock:
                async with async_timeout.timeout(const.TIMEOUT):
                    data = await _async_api_call_with_latency(
                        self, _get_forecast_data_from_api, self.id, self._session
                    )
                if data is None:
                    if not self._had_data_error:
                        _LOGGER.warning(
                            "[%s] Possible API connection problem. Currently unable to download forecast data from MeteoGalicia",
                            self.id,
                        )
                    self._had_data_error = True
                    return None
                if self._had_data_error:
                    _LOGGER.info(
                        "[%s] Forecast data successfully restored after previous error",
                        self.id,
                    )
                    self._had_data_error = False
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching forecast data for {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        async with self._session_lock:
            self._session.close()


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
        self._had_data_error = False
        self.last_api_latency_ms = None
        self.last_api_connected_at = None
        self._session = requests.Session()
        self._session_lock = asyncio.Lock()

    async def _async_update_data(self):
        try:
            async with self._session_lock:
                async with async_timeout.timeout(const.TIMEOUT):
                    data = await _async_api_call_with_latency(
                        self, _get_observation_data_from_api, self.id, self._session
                    )
                if data is None:
                    if not self._had_data_error:
                        _LOGGER.warning(
                            "[%s] Possible API connection problem. Currently unable to download observation data from MeteoGalicia",
                            self.id,
                        )
                    self._had_data_error = True
                    return None
                if self._had_data_error:
                    _LOGGER.info(
                        "[%s] Observation data successfully restored after previous error",
                        self.id,
                    )
                    self._had_data_error = False
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching observation data for {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        async with self._session_lock:
            self._session.close()


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
        self._had_data_error = False
        self.last_api_latency_ms = None
        self.last_api_connected_at = None
        self._session = requests.Session()
        self._session_lock = asyncio.Lock()

    async def _async_update_data(self):
        try:
            async with self._session_lock:
                async with async_timeout.timeout(const.TIMEOUT):
                    data = await _async_api_call_with_latency(
                        self,
                        _get_observation_dailydata_by_station_from_api,
                        self.id,
                        self._session,
                    )
                if data is None:
                    if not self._had_data_error:
                        _LOGGER.warning(
                            "[%s] Possible API connection problem. Currently unable to download daily station data from MeteoGalicia",
                            self.id,
                        )
                    self._had_data_error = True
                    return None
                if self._had_data_error:
                    _LOGGER.info(
                        "[%s] Daily station data successfully restored after previous error",
                        self.id,
                    )
                    self._had_data_error = False
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching daily station data for {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        async with self._session_lock:
            self._session.close()


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
        self._had_data_error = False
        self.last_api_latency_ms = None
        self.last_api_connected_at = None
        self._session = requests.Session()
        self._session_lock = asyncio.Lock()

    async def _async_update_data(self):
        try:
            async with self._session_lock:
                async with async_timeout.timeout(const.TIMEOUT):
                    data = await _async_api_call_with_latency(
                        self,
                        _get_observation_last10mindata_by_station_from_api,
                        self.id,
                        self._session,
                    )
                if data is None:
                    if not self._had_data_error:
                        _LOGGER.warning(
                            "[%s] Possible API connection problem. Currently unable to download last 10 min station data from MeteoGalicia",
                            self.id,
                        )
                    self._had_data_error = True
                    return None
                if self._had_data_error:
                    _LOGGER.info(
                        "[%s] Last 10 min station data successfully restored after previous error",
                        self.id,
                    )
                    self._had_data_error = False
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching last 10 min station data for {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        async with self._session_lock:
            self._session.close()
