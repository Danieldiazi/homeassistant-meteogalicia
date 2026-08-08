"""Tests for config-flow API validation."""

import pytest

from custom_components.meteogalicia import config_flow, const


def test_station_catalog_returns_requested_station():
    station = config_flow._station_from_catalog(
        {"listaEstacionsMeteo": [{"idEstacion": 10124, "estacion": "Santiago-EOAS"}]},
        "10124",
    )

    assert station["estacion"] == "Santiago-EOAS"


def test_station_catalog_rejects_unknown_identifier():
    with pytest.raises(config_flow.InvalidIdentifier):
        config_flow._station_from_catalog({"listaEstacionsMeteo": []}, "99999")


def test_station_measure_parser_supports_last_10_min_payload():
    name, measures = config_flow._station_name_and_measures(
        {
            "listUltimos10min": [
                {
                    "estacion": "Santiago-EOAS",
                    "listaMedidas": [
                        {"codigoParametro": "TA_AVG_1.5m"},
                        {"codigoParametro": "DV_AVG_10m"},
                    ],
                }
            ]
        },
        daily=False,
    )

    assert name == "Santiago-EOAS"
    assert measures == {"TA_AVG_1.5m", "DV_AVG_10m"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (config_flow.CannotConnect(), "cannot_connect"),
        (config_flow.RequestTimeout(), "timeout"),
        (config_flow.InvalidIdentifier(), "unknown_id"),
        (config_flow.InvalidMeasure(), "invalid_measure"),
    ],
)
async def test_validation_errors_are_mapped(monkeypatch, exception, error_key):
    async def raise_validation_error(_hass, _data):
        raise exception

    monkeypatch.setattr(
        config_flow, "_async_validate_api_input", raise_validation_error
    )
    errors = {}

    assert await config_flow._validated_title(object(), {}, errors) is None
    assert errors == {"base": error_key}


@pytest.mark.asyncio
async def test_validation_returns_descriptive_title(monkeypatch):
    async def validate(_hass, data):
        assert data == {const.CONF_ID_CONCELLO: "15009"}
        return "MeteoGalicia Betanzos"

    monkeypatch.setattr(config_flow, "_async_validate_api_input", validate)
    errors = {}

    assert (
        await config_flow._validated_title(
            object(), {const.CONF_ID_CONCELLO: "15009"}, errors
        )
        == "MeteoGalicia Betanzos"
    )
    assert errors == {}
