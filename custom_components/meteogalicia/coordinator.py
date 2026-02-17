# -*- coding: utf-8 -*-
"""Coordinadores de actualización de datos para la integración MeteoGalicia."""
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
except ImportError:  # pragma: no cover - compatibilidad para versiones nuevas/antiguas de HA
    try:
        from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
    except ImportError:  # pragma: no cover - último recurso
        DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

_LOGGER = logging.getLogger(__name__)

# Sesión y cerrojo compartidos para todas las peticiones HTTP
_SHARED_SESSION = requests.Session()
_SHARED_SESSION_LOCK = asyncio.Lock()


def _get_scan_interval(config_scan_interval: timedelta | int | float | None) -> timedelta:
    if isinstance(config_scan_interval, (int, float)):
        return timedelta(seconds=config_scan_interval)
    return config_scan_interval or DEFAULT_SCAN_INTERVAL


async def _async_api_call_with_latency(coordinator, api_call, *args):
    """Llama a la API en un executor, con reintentos y latencia registrada en ms."""
    attempts = 3
    delay = 1
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            data = await coordinator.hass.async_add_executor_job(api_call, *args)
            coordinator.last_api_latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if data is not None:
                # Precisión en segundos para lectura y comparaciones.
                coordinator.last_api_connected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                return data
            last_err = None
        except Exception as err:  # pylint: disable=broad-except
            last_err = err
        if attempt < attempts:
            await asyncio.sleep(delay)
            delay *= 2
    if last_err:
        raise last_err
    return None


def _get_forecast_data_from_api(idc: str, session: requests.Session):
    """Llama a MeteoGalicia para obtener datos de predicción."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_forecast_data(idc)


def _get_observation_data_from_api(idc: str, session: requests.Session):
    """Llama a MeteoGalicia para obtener datos de observación."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_observation_data(idc)


def _get_observation_dailydata_by_station_from_api(ids: str, session: requests.Session):
    """Llama a MeteoGalicia para obtener datos diarios de estación."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_observation_dailydata_by_station(ids)


def _get_observation_last10mindata_by_station_from_api(ids: str, session: requests.Session):
    """Llama a MeteoGalicia para obtener los últimos 10 minutos de una estación."""
    from meteogalicia_api.interface import MeteoGalicia

    meteogalicia_api = MeteoGalicia(session=session, timeout=const.TIMEOUT)
    return meteogalicia_api.get_observation_last10mindata_by_station(ids)


class BaseMeteoGaliciaCoordinator(DataUpdateCoordinator):
    """Plantilla común de coordinador para los endpoints de MeteoGalicia."""

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
        self._session = _SHARED_SESSION
        self._session_lock = _SHARED_SESSION_LOCK

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
                f"Error obteniendo {self._error_context} para {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        # No cerramos la sesión compartida aquí para evitar interferir con otros coordinadores.
        return


class MeteoGaliciaForecastCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinador de datos de predicción."""

    def __init__(self, hass: HomeAssistant, id_concello: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_concello,
            scan_interval=scan_interval,
            name_suffix="forecast",
            api_fn=_get_forecast_data_from_api,
            warn_msg="[%s] Posible problema de conexión. No se pueden descargar datos de predicción de MeteoGalicia",
            restore_msg="[%s] Datos de predicción recuperados tras el error previo",
            error_context="datos de predicción",
        )


class MeteoGaliciaObservationCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinador de datos de observación."""

    def __init__(self, hass: HomeAssistant, id_concello: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_concello,
            scan_interval=scan_interval,
            name_suffix="observation",
            api_fn=_get_observation_data_from_api,
            warn_msg="[%s] Posible problema de conexión. No se pueden descargar datos de observación de MeteoGalicia",
            restore_msg="[%s] Datos de observación recuperados tras el error previo",
            error_context="datos de observación",
        )


class MeteoGaliciaStationDailyCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinador de datos diarios de estación."""

    def __init__(self, hass: HomeAssistant, id_estacion: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_estacion,
            scan_interval=scan_interval,
            name_suffix="station_daily",
            api_fn=_get_observation_dailydata_by_station_from_api,
            warn_msg="[%s] Posible problema de conexión. No se pueden descargar datos diarios de MeteoGalicia",
            restore_msg="[%s] Datos diarios recuperados tras el error previo",
            error_context="datos diarios de estación",
        )


class MeteoGaliciaStationLast10MinCoordinator(BaseMeteoGaliciaCoordinator):
    """Coordinador de datos de los últimos 10 minutos de estación."""

    def __init__(self, hass: HomeAssistant, id_estacion: str, scan_interval) -> None:
        super().__init__(
            hass=hass,
            id_value=id_estacion,
            scan_interval=scan_interval,
            name_suffix="station_last10min",
            api_fn=_get_observation_last10mindata_by_station_from_api,
            warn_msg="[%s] Posible problema de conexión. No se pueden descargar datos de los últimos 10 minutos de MeteoGalicia",
            restore_msg="[%s] Datos de los últimos 10 minutos recuperados tras el error previo",
            error_context="datos de últimos 10 minutos de estación",
        )
