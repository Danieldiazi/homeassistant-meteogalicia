"""Tests for actual observation timestamps and stale-data detection."""

from datetime import datetime, timezone

import pytest

from custom_components.meteogalicia import coordinator as coordinator_module
from custom_components.meteogalicia.coordinator import (
    MeteoGaliciaObservationCoordinator,
    MeteoGaliciaStationDailyCoordinator,
    MeteoGaliciaStationLast10MinCoordinator,
    _parse_api_timestamp,
)


def test_api_timestamp_parser_normalises_naive_utc_values():
    assert _parse_api_timestamp("2026-08-08T16:17:00").isoformat() == (
        "2026-08-08T16:17:00+00:00"
    )
    assert _parse_api_timestamp("invalid") is None
    assert _parse_api_timestamp(None) is None


@pytest.mark.parametrize(
    ("coordinator_class", "payload", "expected_timestamp"),
    [
        (
            MeteoGaliciaObservationCoordinator,
            {"listaObservacionConcellos": [{"dataUTC": "2026-08-08T16:17:00"}]},
            "2026-08-08T16:17:00+00:00",
        ),
        (
            MeteoGaliciaStationLast10MinCoordinator,
            {"listUltimos10min": [{"instanteLecturaUTC": "2026-08-08T16:10:00"}]},
            "2026-08-08T16:10:00+00:00",
        ),
        (
            MeteoGaliciaStationDailyCoordinator,
            {"listDatosDiarios": [{"data": "2026-08-08T00:00:00"}]},
            "2026-08-08T00:00:00+00:00",
        ),
    ],
)
async def test_coordinators_extract_real_observation_timestamp(
    hass, monkeypatch, coordinator_class, payload, expected_timestamp
):
    monkeypatch.setattr(
        coordinator_module,
        "_utcnow",
        lambda: datetime(2026, 8, 8, 16, 20, tzinfo=timezone.utc),
    )
    coordinator = coordinator_class(hass, "15009", 1800)

    coordinator._update_data_timestamp(payload)

    assert coordinator.data_timestamp == expected_timestamp
    assert coordinator.data_age_seconds is not None
    await coordinator.async_close()


async def test_recent_observation_becomes_stale_after_two_scan_intervals(
    hass, monkeypatch, caplog
):
    current_time = datetime(2026, 8, 8, 17, 18, tzinfo=timezone.utc)
    monkeypatch.setattr(coordinator_module, "_utcnow", lambda: current_time)
    coordinator = MeteoGaliciaObservationCoordinator(hass, "15009", 1800)

    coordinator._update_data_timestamp(
        {"listaObservacionConcellos": [{"dataUTC": "2026-08-08T16:17:00"}]}
    )

    assert coordinator.data_age_seconds == 3660.0
    assert coordinator.data_is_stale is True
    assert "están obsoletos" in caplog.text

    current_time = datetime(2026, 8, 8, 17, 20, tzinfo=timezone.utc)
    coordinator._update_data_timestamp(
        {"listaObservacionConcellos": [{"dataUTC": "2026-08-08T17:17:00"}]}
    )
    assert coordinator.data_is_stale is False
    assert "vuelve a proporcionar datos recientes" in caplog.text
    await coordinator.async_close()


async def test_daily_observation_uses_a_48_hour_threshold(hass, monkeypatch):
    monkeypatch.setattr(
        coordinator_module,
        "_utcnow",
        lambda: datetime(2026, 8, 8, 0, 0, 1, tzinfo=timezone.utc),
    )
    coordinator = MeteoGaliciaStationDailyCoordinator(hass, "10124", 1800)
    coordinator._update_data_timestamp(
        {"listDatosDiarios": [{"data": "2026-08-06T00:00:00"}]}
    )

    assert coordinator.data_is_stale is True
    await coordinator.async_close()
