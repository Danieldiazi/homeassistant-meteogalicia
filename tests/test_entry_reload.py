"""Tests for config-entry option reloads."""

import pytest

from custom_components.meteogalicia import async_reload_entry


@pytest.mark.asyncio
async def test_options_update_reloads_entry():
    calls = []

    class ConfigEntries:
        async def async_reload(self, entry_id):
            calls.append(entry_id)

    class Hass:
        config_entries = ConfigEntries()

    class Entry:
        entry_id = "entry-id"

    await async_reload_entry(Hass(), Entry())

    assert calls == ["entry-id"]
