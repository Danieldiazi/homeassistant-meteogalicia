"""Tests for coordinator failures and recovery."""

import asyncio
from types import SimpleNamespace

import pytest

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.meteogalicia import coordinator as coordinator_module
from custom_components.meteogalicia.coordinator import BaseMeteoGaliciaCoordinator


def _coordinator_double():
    return SimpleNamespace(
        _session=object(),
        _api_fn=object(),
        _error_context="datos de prueba",
        _warn_msg="No hay datos para %s",
        _restore_msg="Datos recuperados para %s",
        _had_data_error=False,
        id="15009",
        _update_data_timestamp=lambda _data: None,
        _check_staleness_transition=lambda: None,
    )


@pytest.mark.asyncio
async def test_empty_response_is_a_failed_update(monkeypatch):
    async def return_empty(*_args):
        return None

    monkeypatch.setattr(
        coordinator_module, "_async_api_call_with_latency", return_empty
    )
    coordinator = _coordinator_double()

    with pytest.raises(UpdateFailed, match="no devolvió"):
        await BaseMeteoGaliciaCoordinator._async_update_data(coordinator)

    assert coordinator._had_data_error is True


@pytest.mark.asyncio
async def test_success_after_empty_response_clears_error(monkeypatch):
    payload = {"predConcello": {"nome": "Betanzos"}}

    async def return_payload(*_args):
        return payload

    monkeypatch.setattr(
        coordinator_module, "_async_api_call_with_latency", return_payload
    )
    coordinator = _coordinator_double()
    coordinator._had_data_error = True

    assert await BaseMeteoGaliciaCoordinator._async_update_data(coordinator) == payload
    assert coordinator._had_data_error is False


@pytest.mark.asyncio
async def test_independent_coordinators_are_not_globally_serialized(monkeypatch):
    running = 0
    maximum_running = 0

    async def concurrent_call(*_args):
        nonlocal running, maximum_running
        running += 1
        maximum_running = max(maximum_running, running)
        await asyncio.sleep(0)
        running -= 1
        return {"data": True}

    monkeypatch.setattr(
        coordinator_module, "_async_api_call_with_latency", concurrent_call
    )

    await asyncio.gather(
        BaseMeteoGaliciaCoordinator._async_update_data(_coordinator_double()),
        BaseMeteoGaliciaCoordinator._async_update_data(_coordinator_double()),
    )

    assert maximum_running == 2


@pytest.mark.asyncio
async def test_coordinator_closes_its_own_session_in_executor():
    closed = []
    session = SimpleNamespace(close=lambda: closed.append(True))

    async def executor_job(callback):
        callback()

    coordinator = SimpleNamespace(
        hass=SimpleNamespace(async_add_executor_job=executor_job),
        _session=session,
    )

    await BaseMeteoGaliciaCoordinator.async_close(coordinator)

    assert closed == [True]
