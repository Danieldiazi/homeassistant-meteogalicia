"""Data update coordinators for MeteoGalicia integration."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import asyncio
import logging
import time
from typing import Callable, Any

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
        coordinator.last_api_connected_at = datetime.now(timezone.utc).isoformat()
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


class BaseMeteoGaliciaCoordinator(DataUpdateCoordinator):
    """Shared coordinator boilerplate for MeteoGalicia endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        id_value: str,
        scan_interval,
        name_suffix: str,
        api_fn: Callable[[str, requests.Session], Any],
        warn_msg: str,
        restore_msg: str,
        error_context: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{const.DOMAIN}_{name_suffix}_{id_value}",
            update_interval=_get_scan_interval(scan_interval),
        )
        self.id = id_value
        self._api_fn = api_fn
        self._warn_msg = warn_msg
        self._restore_msg = restore_msg
        self._error_context = error_context
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
                        self, self._api_fn, self.id, self._session
                    )
                if data is None:
                    if not self._had_data_error:
                        _LOGGER.warning(self._warn_msg, self.id)
                    self._had_data_error = True
                    return None
                if self._had_data_error:
                    _LOGGER.info(self._restore_msg, self.id)
                    self._had_data_error = False
                return data
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Error fetching {self._error_context} for {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        async with self._session_lock:
            self._session.close()


class MeteoGaliciaForecastCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinator for forecast data."""

    def __init__(self, hass: HomeAssistant, id_concello: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_concello,
            scan_interval=scan_interval,
            name_suffix="forecast",
            api_fn=_get_forecast_data_from_api,
            warn_msg="[%s] Possible API connection problem. Currently unable to download forecast data from MeteoGalicia",
            restore_msg="[%s] Forecast data successfully restored after previous error",
            error_context="forecast data",
        )


class MeteoGaliciaObservationCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinator for observation data."""

    def __init__(self, hass: HomeAssistant, id_concello: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_concello,
            scan_interval=scan_interval,
            name_suffix="observation",
            api_fn=_get_observation_data_from_api,
            warn_msg="[%s] Possible API connection problem. Currently unable to download observation data from MeteoGalicia",
            restore_msg="[%s] Observation data successfully restored after previous error",
            error_context="observation data",
        )


class MeteoGaliciaStationDailyCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinator for station daily data."""

    def __init__(self, hass: HomeAssistant, id_estacion: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_estacion,
            scan_interval=scan_interval,
            name_suffix="station_daily",
            api_fn=_get_observation_dailydata_by_station_from_api,
            warn_msg="[%s] Possible API connection problem. Currently unable to download daily station data from MeteoGalicia",
            restore_msg="[%s] Daily station data successfully restored after previous error",
            error_context="daily station data",
        )


class MeteoGaliciaStationLast10MinCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinator for station last 10 min data."""

    def __init__(self, hass: HomeAssistant, id_estacion: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_estacion,
            scan_interval=scan_interval,
            name_suffix="station_last10min",
            api_fn=_get_observation_last10mindata_by_station_from_api,
            warn_msg="[%s] Possible API connection problem. Currently unable to download last 10 min station data from MeteoGalicia",
            restore_msg="[%s] Last 10 min station data successfully restored after previous error",
            error_context="last 10 min station data",
        )
