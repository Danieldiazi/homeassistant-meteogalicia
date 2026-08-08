"""Tests for shared config-entry coordinators."""
import asyncio

import pytest

from custom_components.meteogalicia import const
from custom_components.meteogalicia.coordinator import async_get_entry_coordinator


class DummyHass:
    """Minimal Home Assistant stand-in used by the coordinator cache."""

    def __init__(self):
        self.data = {}

    @staticmethod
    def async_create_task(coro):
        return asyncio.create_task(coro)


class CountingCoordinator:
    """Coordinator that records construction and first refreshes."""

    created = 0
    refreshed = 0

    def __init__(self, hass, id_value, scan_interval):
        type(self).created += 1
        self.id = id_value
        self.scan_interval = scan_interval

    async def async_refresh(self):
        type(self).refreshed += 1
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_entry_platforms_share_one_coordinator_and_refresh(monkeypatch):
    monkeypatch.setattr(CountingCoordinator, "created", 0)
    monkeypatch.setattr(CountingCoordinator, "refreshed", 0)
    hass = DummyHass()

    first, second = await asyncio.gather(
        async_get_entry_coordinator(
            hass, "entry", CountingCoordinator, "15030", 1200
        ),
        async_get_entry_coordinator(
            hass, "entry", CountingCoordinator, "15030", 1200
        ),
    )

    assert first is second
    assert first.scan_interval == 1200
    assert CountingCoordinator.created == 1
    assert CountingCoordinator.refreshed == 1
    assert hass.data[const.DOMAIN]["entry"]["coordinators"] == [first]


@pytest.mark.asyncio
async def test_different_entries_do_not_share_coordinators(monkeypatch):
    monkeypatch.setattr(CountingCoordinator, "created", 0)
    monkeypatch.setattr(CountingCoordinator, "refreshed", 0)
    hass = DummyHass()

    first = await async_get_entry_coordinator(
        hass, "entry-1", CountingCoordinator, "15030", 1200
    )
    second = await async_get_entry_coordinator(
        hass, "entry-2", CountingCoordinator, "15030", 1200
    )

    assert first is not second
    assert CountingCoordinator.created == 2
    assert CountingCoordinator.refreshed == 2


@pytest.mark.asyncio
async def test_failed_initialization_can_be_retried(monkeypatch):
    class FailingCoordinator(CountingCoordinator):
        failures = 1

        async def async_refresh(self):
            if type(self).failures:
                type(self).failures -= 1
                raise TimeoutError
            await super().async_refresh()

    monkeypatch.setattr(FailingCoordinator, "created", 0)
    monkeypatch.setattr(FailingCoordinator, "refreshed", 0)
    monkeypatch.setattr(FailingCoordinator, "failures", 1)
    hass = DummyHass()

    with pytest.raises(TimeoutError):
        await async_get_entry_coordinator(
            hass, "entry", FailingCoordinator, "15030", 1200
        )

    coordinator = await async_get_entry_coordinator(
        hass, "entry", FailingCoordinator, "15030", 1200
    )

    assert coordinator.id == "15030"
    assert FailingCoordinator.created == 2
    assert hass.data[const.DOMAIN]["entry"]["coordinators"] == [coordinator]
