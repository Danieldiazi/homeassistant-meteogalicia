"""Tests for the guided MeteoGalicia config flow."""

import pytest

from custom_components.meteogalicia import config_flow, const


@pytest.mark.asyncio
async def test_forecast_catalog_selection_passes_only_concello_id(monkeypatch):
    flow = config_flow.MeteoGaliciaConfigFlow()
    flow.hass = object()
    flow._selected_province = "A Coruña"

    async def get_concellos(_hass, province):
        assert province == "A Coruña"
        return [
            {
                "idConcello": "15078",
                "concello": "Santiago de Compostela",
                "provincia": "A Coruña",
            }
        ]

    captured = {}

    async def capture_forecast(user_input=None):
        captured.update(user_input or {})
        return {"type": "captured"}

    monkeypatch.setattr(config_flow, "_async_get_concellos", get_concellos)
    monkeypatch.setattr(flow, "async_step_forecast", capture_forecast)

    result = await flow.async_step_forecast_concello(
        {const.CONF_ID_CONCELLO: "15078"}
    )

    assert result == {"type": "captured"}
    assert captured == {const.CONF_ID_CONCELLO: "15078"}


@pytest.mark.asyncio
async def test_station_catalog_selection_passes_station_id(monkeypatch):
    flow = config_flow.MeteoGaliciaConfigFlow()
    flow.hass = object()
    flow._selected_province = "A Coruña"
    flow._selected_station_concello = "Santiago de Compostela"

    async def get_stations(_hass, province, concello=None):
        assert province == "A Coruña"
        assert concello == "Santiago de Compostela"
        return [
            {
                "idEstacion": 10124,
                "estacion": "Santiago-EOAS",
                "provincia": "A Coruña",
                "concello": "Santiago de Compostela",
            }
        ]

    captured = {}

    async def capture_station(user_input=None):
        captured.update(user_input or {})
        return {"type": "captured"}

    monkeypatch.setattr(config_flow, "_async_get_stations", get_stations)
    monkeypatch.setattr(flow, "async_step_station", capture_station)

    result = await flow.async_step_station_select(
        {
            const.CONF_ID_ESTACION: "10124",
            const.CONF_ID_ESTACION_MEDIDA_DAILY: "BH_SUM_1.5m",
        }
    )

    assert result == {"type": "captured"}
    assert captured == {
        const.CONF_ID_ESTACION: "10124",
        const.CONF_ID_ESTACION_MEDIDA_DAILY: "BH_SUM_1.5m",
    }


@pytest.mark.asyncio
async def test_station_concellos_come_from_station_catalog(monkeypatch):
    flow = config_flow.MeteoGaliciaConfigFlow()
    flow.hass = object()
    flow._selected_province = "A Coruña"

    async def get_stations(_hass, province, concello=None):
        assert province == "A Coruña"
        assert concello is None
        return [
            {
                "idEstacion": 10124,
                "estacion": "Santiago-EOAS",
                "provincia": "A Coruña",
                "concello": "Santiago de Compostela",
            },
            {
                "idEstacion": 10045,
                "estacion": "A Coruña",
                "provincia": "A Coruña",
                "concello": "A Coruña",
            },
            {
                "idEstacion": 10125,
                "estacion": "Santiago-Campus",
                "provincia": "A Coruña",
                "concello": "Santiago de Compostela",
            },
        ]

    monkeypatch.setattr(config_flow, "_async_get_stations", get_stations)

    result = await flow.async_step_station_concello()

    selector = next(iter(result["data_schema"].schema.values()))
    values = [option["value"] for option in selector.config["options"]]

    assert values == ["A Coruña", "Santiago de Compostela"]


@pytest.mark.asyncio
async def test_manual_station_path_is_preserved(monkeypatch):
    flow = config_flow.MeteoGaliciaConfigFlow()

    async def capture_station(user_input=None):
        assert user_input is None
        return {"type": "manual"}

    monkeypatch.setattr(flow, "async_step_station", capture_station)

    result = await flow.async_step_station_method(
        {config_flow.CONF_CONFIGURATION_METHOD: config_flow.CONFIGURATION_METHOD_MANUAL}
    )

    assert result == {"type": "manual"}
