# -*- coding: utf-8 -*-
"""Coordinadores de actualización de datos para la integración MeteoGalicia."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import asyncio
import logging
import time
from typing import Callable, Any

import requests

from homeassistant.core import HomeAssistant

try:
    from homeassistant.helpers.entity_platform import DEFAULT_SCAN_INTERVAL
except (
    ImportError
):  # pragma: no cover - compatibilidad para versiones nuevas/antiguas de HA
    try:
        from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
    except ImportError:  # pragma: no cover - último recurso
        DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

_LOGGER = logging.getLogger(__name__)

_MIN_RECENT_DATA_MAX_AGE = timedelta(minutes=30)
_DAILY_DATA_MAX_AGE = timedelta(hours=48)


def _utcnow() -> datetime:
    """Return the current UTC time for freshness calculations."""
    return datetime.now(timezone.utc)


def _parse_api_timestamp(value: Any) -> datetime | None:
    """Parse MeteoGalicia timestamps, whose UTC values omit the offset."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first_mapping(data: dict, key: str) -> dict | None:
    """Return the first mapping from a payload list."""
    if not isinstance(data, dict):
        return None
    items = data.get(key)
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None
    return items[0]


def _observation_timestamp(data: dict) -> Any:
    observation = _first_mapping(data, "listaObservacionConcellos")
    return observation.get("dataUTC") if observation else None


def _station_daily_timestamp(data: dict) -> Any:
    day = _first_mapping(data, "listDatosDiarios")
    return day.get("data") if day else None


def _station_last10_timestamp(data: dict) -> Any:
    observation = _first_mapping(data, "listUltimos10min")
    return observation.get("instanteLecturaUTC") if observation else None


async def async_get_entry_coordinator(
    hass: HomeAssistant,
    entry_id: str,
    coordinator_class,
    id_value: str,
    scan_interval,
):
    """Return one initialized coordinator per config entry, class and id.

    Sensor and weather platforms are loaded concurrently by Home Assistant.  Keeping
    the initialization task in the entry data makes both platforms await the same
    first refresh instead of creating duplicate API polling loops.
    """
    entry_data = hass.data.setdefault(const.DOMAIN, {}).setdefault(entry_id, {})
    tasks = entry_data.setdefault("coordinator_tasks", {})
    key = (coordinator_class.__name__, id_value)
    task = tasks.get(key)

    if task is None:

        async def _async_create_and_refresh():
            coordinator = coordinator_class(hass, id_value, scan_interval)
            coordinators = entry_data.setdefault("coordinators", [])
            coordinators.append(coordinator)
            try:
                await coordinator.async_refresh()
            except Exception:
                coordinators.remove(coordinator)
                raise
            return coordinator

        task = hass.async_create_task(_async_create_and_refresh())
        tasks[key] = task

    try:
        return await task
    except Exception:
        # Allow Home Assistant to retry platform setup after an unexpected failure.
        if tasks.get(key) is task:
            tasks.pop(key, None)
        raise


def _get_scan_interval(
    config_scan_interval: timedelta | int | float | None,
) -> timedelta:
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
            coordinator.last_api_latency_ms = round(
                (time.perf_counter() - started) * 1000.0, 2
            )
            if data is not None:
                # Precisión en segundos para lectura y comparaciones.
                coordinator.last_api_connected_at = datetime.now(
                    timezone.utc
                ).isoformat(timespec="seconds")
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


def _get_observation_last10mindata_by_station_from_api(
    ids: str, session: requests.Session
):
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
        data_timestamp_fn: Callable[[dict], Any] | None = None,
        data_max_age: timedelta | None = None,
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
        self.data_timestamp = None
        self._data_timestamp_utc = None
        self._data_timestamp_fn = data_timestamp_fn
        self._data_max_age = data_max_age
        self._last_stale_state = None
        # Each coordinator owns its session. DataUpdateCoordinator already prevents
        # overlapping refreshes for the same coordinator, while independent entries
        # and endpoints can now update concurrently.
        self._session = requests.Session()

    @property
    def data_age_seconds(self) -> float | None:
        """Return the age of the actual MeteoGalicia observation."""
        if self._data_timestamp_utc is None:
            return None
        return round(
            max(0.0, (_utcnow() - self._data_timestamp_utc).total_seconds()),
            1,
        )

    @property
    def data_is_stale(self) -> bool | None:
        """Return whether the actual observation is older than expected."""
        age = self.data_age_seconds
        if age is None:
            return None
        max_age = self._data_max_age or max(
            _MIN_RECENT_DATA_MAX_AGE,
            self.update_interval * 2,
        )
        return age > max_age.total_seconds()

    def _check_staleness_transition(self) -> None:
        """Log only when measured data becomes stale or recovers."""
        stale = self.data_is_stale
        if stale is True and self._last_stale_state is not True:
            _LOGGER.warning(
                "[%s] Los datos medidos de MeteoGalicia están obsoletos "
                "(marca temporal: %s, antigüedad: %s s)",
                self.id,
                self.data_timestamp,
                self.data_age_seconds,
            )
        elif stale is False and self._last_stale_state is True:
            _LOGGER.info(
                "[%s] MeteoGalicia vuelve a proporcionar datos recientes", self.id
            )
        self._last_stale_state = stale

    def _update_data_timestamp(self, data: dict) -> None:
        """Store the real observation time returned by MeteoGalicia."""
        if self._data_timestamp_fn is None:
            return
        timestamp = _parse_api_timestamp(self._data_timestamp_fn(data))
        self._data_timestamp_utc = timestamp
        self.data_timestamp = (
            timestamp.isoformat(timespec="seconds") if timestamp else None
        )
        self._check_staleness_transition()

    async def _async_update_data(self):
        try:
            async with asyncio.timeout(const.TIMEOUT):
                data = await _async_api_call_with_latency(
                    self, self._api_fn, self.id, self._session
                )
            if data is None:
                if not self._had_data_error:
                    _LOGGER.warning(self._warn_msg, self.id)
                self._had_data_error = True
                raise UpdateFailed(
                    f"MeteoGalicia no devolvió {self._error_context} para {self.id}"
                )
            if self._had_data_error:
                _LOGGER.info(self._restore_msg, self.id)
                self._had_data_error = False
            self._update_data_timestamp(data)
            return data
        except UpdateFailed:
            self._check_staleness_transition()
            raise
        except Exception as err:  # pylint: disable=broad-except
            self._check_staleness_transition()
            raise UpdateFailed(
                f"Error obteniendo {self._error_context} para {self.id}: {err}"
            ) from err

    async def async_close(self) -> None:
        """Close this coordinator's HTTP resources."""
        await self.hass.async_add_executor_job(self._session.close)


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
            data_timestamp_fn=_observation_timestamp,
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
            data_timestamp_fn=_station_daily_timestamp,
            data_max_age=_DAILY_DATA_MAX_AGE,
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
            data_timestamp_fn=_station_last10_timestamp,
        )
