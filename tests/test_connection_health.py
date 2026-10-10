"""Regression tests for executor lifetime and useful connection diagnostics."""

import asyncio
from datetime import timedelta
from threading import Event
from unittest.mock import Mock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from meteogalicia_api.errors import (
    MeteoGaliciaHTTPError,
    MeteoGaliciaInvalidResponseError,
)

from custom_components.meteogalicia import coordinator as module
from custom_components.meteogalicia.coordinator import (
    MeteoGaliciaObservationCoordinator,
)


async def test_shutdown_waits_for_timed_out_executor(hass, monkeypatch):
    started, release = Event(), Event()
    closed = Mock()
    calls = []

    def blocked_request(*_args):
        calls.append(True)
        started.set()
        assert release.wait(5)
        return {"listaObservacionConcellos": []}

    monkeypatch.setattr(module.const, "TIMEOUT", 0.05)
    coordinator = MeteoGaliciaObservationCoordinator(hass, "15009", 600)
    coordinator._api_fn = blocked_request
    coordinator._session.close = closed
    try:
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert started.is_set()
        shutdown = asyncio.create_task(coordinator.async_shutdown())
        await asyncio.sleep(0)
        assert not shutdown.done()
        closed.assert_not_called()
    finally:
        release.set()
    await shutdown
    closed.assert_called_once()
    with pytest.raises(RuntimeError, match="shut down"):
        await hass.async_add_executor_job(coordinator._locked_api_call, blocked_request)
    assert len(calls) == 1


async def test_rate_limit_skips_immediate_retry_and_recovers(hass):
    coordinator = MeteoGaliciaObservationCoordinator(hass, "15009", 600)
    api = Mock(side_effect=MeteoGaliciaHTTPError(429, retry_after=3600))
    coordinator._api_fn = api
    try:
        with pytest.raises(UpdateFailed, match="429"):
            await coordinator._async_update_data()
        assert api.call_count == 1
        assert coordinator.consecutive_failures == 1
        assert coordinator.last_failure_kind == "http"
        assert coordinator.update_interval == timedelta(hours=1)
        assert coordinator.last_success is None
        api.side_effect = None
        api.return_value = {"listaObservacionConcellos": []}
        await coordinator._async_update_data()
        assert coordinator.last_success is not None
        assert coordinator.consecutive_failures == 0
        assert coordinator.last_failure_kind is None
        assert coordinator.update_interval == timedelta(minutes=10)
    finally:
        await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "error",
    [
        MeteoGaliciaHTTPError(404),
        MeteoGaliciaInvalidResponseError("Malformed JSON"),
    ],
)
async def test_nonretryable_errors_are_not_retried(hass, error):
    coordinator = MeteoGaliciaObservationCoordinator(hass, "15009", 600)
    api = Mock(side_effect=error)
    coordinator._api_fn = api
    try:
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert api.call_count == 1
        assert coordinator.last_failure_kind == error.kind
    finally:
        await coordinator.async_shutdown()
