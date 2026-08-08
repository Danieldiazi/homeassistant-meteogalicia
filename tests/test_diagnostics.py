"""Tests for MeteoGalicia config-entry diagnostics."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from custom_components.meteogalicia import diagnostics


@pytest.mark.asyncio
async def test_diagnostics_include_health_interval_errors_and_entities(monkeypatch):
    coordinator = SimpleNamespace(
        name="meteogalicia_observation_15009",
        id="15009",
        update_interval=timedelta(seconds=1800),
        last_update_success=False,
        last_api_connected_at="2026-08-08T16:17:00+00:00",
        last_api_latency_ms=243.2,
        last_exception=TimeoutError("API timeout"),
        data={"private_payload": "not exposed"},
    )
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Betanzos",
        data={"id_concello": "15009"},
        options={"scan_interval": 1800},
    )
    entity = SimpleNamespace(
        entity_id="weather.betanzos",
        unique_id="meteogalicia_weather_15009",
        platform="meteogalicia",
        disabled_by=None,
    )
    hass = SimpleNamespace(
        data={"meteogalicia": {"entry-1": {"coordinators": [coordinator]}}}
    )
    monkeypatch.setattr(diagnostics.er, "async_get", lambda _hass: object())
    monkeypatch.setattr(
        diagnostics.er,
        "async_entries_for_config_entry",
        lambda _registry, _entry_id: [entity],
    )

    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["type"] == "municipality"
    assert result["coordinators"][0]["scan_interval_seconds"] == 1800
    assert result["coordinators"][0]["last_error"] == "API timeout"
    assert result["entities"][0]["entity_id"] == "weather.betanzos"
    assert "private_payload" not in str(result)
