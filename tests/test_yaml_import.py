"""Tests for importing legacy MeteoGalicia YAML configuration."""
from datetime import timedelta

import pytest

from custom_components.meteogalicia import const, sensor
from custom_components.meteogalicia.config_flow import _unique_id_from_data
from custom_components.meteogalicia.sensor import (
    _yaml_configuration,
    _yaml_import_data,
    _yaml_issue_id,
)


def test_yaml_forecast_import_preserves_interval():
    data = _yaml_import_data(
        {
            const.CONF_ID_CONCELLO: "15009",
            "scan_interval": timedelta(seconds=1700),
        }
    )

    assert data == {
        const.CONF_ID_CONCELLO: "15009",
        "scan_interval": 1700,
    }
    assert _unique_id_from_data(data) == "concello_15009"
    assert _yaml_configuration(data) == (
        "sensor:\n"
        "  - platform: meteogalicia\n"
        "    id_concello: 15009\n"
        "    scan_interval: 1700"
    )


def test_yaml_station_import_preserves_measure_and_has_stable_issue_id():
    data = _yaml_import_data(
        {
            const.CONF_ID_ESTACION: "10124",
            const.CONF_ID_ESTACION_MEDIDA_DAILY: "BH_SUM_1.5m",
            "scan_interval": timedelta(seconds=1800),
        }
    )

    assert _unique_id_from_data(data) == "estacion_10124_BH_SUM_1.5m_"
    assert _yaml_issue_id(data) == "yaml_imported_10124_BH_SUM_1_5m"
    assert "id_estacion_medida_diarios: BH_SUM_1.5m" in _yaml_configuration(data)


def test_different_station_measures_create_different_imports():
    daily = {
        const.CONF_ID_ESTACION: "10124",
        const.CONF_ID_ESTACION_MEDIDA_DAILY: "BH_SUM_1.5m",
    }
    last10 = {
        const.CONF_ID_ESTACION: "10124",
        const.CONF_ID_ESTACION_MEDIDA_LAST10MIN: "DV_AVG_10m",
    }

    assert _unique_id_from_data(daily) != _unique_id_from_data(last10)
    assert _yaml_issue_id(daily) != _yaml_issue_id(last10)


@pytest.mark.asyncio
async def test_yaml_platform_imports_entry_and_creates_repair(monkeypatch):
    flow_calls = []
    issue_calls = []

    class FlowManager:
        async def async_init(self, domain, *, context, data):
            flow_calls.append((domain, context, data))
            return {"type": "create_entry"}

    class ConfigEntries:
        flow = FlowManager()

    class Hass:
        config_entries = ConfigEntries()

    monkeypatch.setattr(
        sensor.ir,
        "async_create_issue",
        lambda *args, **kwargs: issue_calls.append((args, kwargs)),
    )

    await sensor.async_setup_platform(
        Hass(),
        {
            const.CONF_ID_CONCELLO: "15009",
            "scan_interval": timedelta(seconds=1700),
        },
        lambda entities: pytest.fail(f"Unexpected YAML entities: {entities}"),
    )

    assert flow_calls == [
        (
            const.DOMAIN,
            {"source": sensor.config_entries.SOURCE_IMPORT},
            {const.CONF_ID_CONCELLO: "15009", "scan_interval": 1700},
        )
    ]
    assert len(issue_calls) == 1
    assert issue_calls[0][1]["translation_key"] == "yaml_imported"
    assert issue_calls[0][1]["is_persistent"] is False


@pytest.mark.asyncio
async def test_invalid_yaml_import_does_not_claim_success(monkeypatch):
    class FlowManager:
        async def async_init(self, domain, *, context, data):
            return {"type": "abort", "reason": "invalid_import"}

    class ConfigEntries:
        flow = FlowManager()

    class Hass:
        config_entries = ConfigEntries()

    monkeypatch.setattr(
        sensor.ir,
        "async_create_issue",
        lambda *args, **kwargs: pytest.fail("Unexpected Repairs issue"),
    )

    await sensor.async_setup_platform(Hass(), {}, lambda entities: None)
