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


def counting_coordinator(stats):
    """Create an isolated coordinator double backed by per-test counters."""

    class CountingCoordinator:
        def __init__(self, hass, id_value, scan_interval):
            stats["created"] += 1
            self.id = id_value
            self.scan_interval = scan_interval

        async def async_refresh(self):
            stats["refreshed"] += 1
            if stats["failures"]:
                stats["failures"] -= 1
                raise TimeoutError
            await asyncio.sleep(0)

    return CountingCoordinator


@pytest.mark.asyncio
async def test_entry_platforms_share_one_coordinator_and_refresh():
    stats = {"created": 0, "refreshed": 0, "failures": 0}
    coordinator_class = counting_coordinator(stats)
    hass = DummyHass()

    first, second = await asyncio.gather(
        async_get_entry_coordinator(
            hass, "entry", coordinator_class, "15030", 1200
        ),
        async_get_entry_coordinator(
            hass, "entry", coordinator_class, "15030", 1200
        ),
    )

    assert first is second
    assert first.scan_interval == 1200
    assert stats["created"] == 1
    assert stats["refreshed"] == 1
    assert hass.data[const.DOMAIN]["entry"]["coordinators"] == [first]


@pytest.mark.asyncio
async def test_different_entries_do_not_share_coordinators():
    stats = {"created": 0, "refreshed": 0, "failures": 0}
    coordinator_class = counting_coordinator(stats)
    hass = DummyHass()

    first = await async_get_entry_coordinator(
        hass, "entry-1", coordinator_class, "15030", 1200
    )
    second = await async_get_entry_coordinator(
        hass, "entry-2", coordinator_class, "15030", 1200
    )

    assert first is not second
    assert stats["created"] == 2
    assert stats["refreshed"] == 2


@pytest.mark.asyncio
async def test_failed_initialization_can_be_retried():
    stats = {"created": 0, "refreshed": 0, "failures": 1}
    coordinator_class = counting_coordinator(stats)
    hass = DummyHass()

    with pytest.raises(TimeoutError):
        await async_get_entry_coordinator(
            hass, "entry", coordinator_class, "15030", 1200
        )

    coordinator = await async_get_entry_coordinator(
        hass, "entry", coordinator_class, "15030", 1200
    )

    assert coordinator.id == "15030"
    assert stats["created"] == 2
    assert hass.data[const.DOMAIN]["entry"]["coordinators"] == [coordinator]
