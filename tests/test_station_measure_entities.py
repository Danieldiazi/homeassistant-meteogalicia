"""Tests for typed station measurement entities."""

from types import SimpleNamespace

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

from custom_components.meteogalicia import const
from custom_components.meteogalicia.sensor import (
    _station_measure_description,
    _station_measure_entities,
    setup_id_estacion_platform,
)


def _measure(code, name, unit, value=1, validation=1):
    return {
        "codigoParametro": code,
        "nomeParametro": name,
        "unidade": unit,
        "valor": value,
        "lnCodigoValidacion": validation,
    }


def test_measure_descriptions_map_native_home_assistant_metadata():
    cases = [
        ("TA_AVG_1.5m", "ºC", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
        ("HR_AVG_1.5m", "%", SensorDeviceClass.HUMIDITY, "%"),
        (
            "PR_AVG_1.5m",
            "hPa",
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.HPA,
        ),
        (
            "PP_SUM_1.5m",
            "L/m2",
            SensorDeviceClass.PRECIPITATION,
            UnitOfPrecipitationDepth.MILLIMETERS,
        ),
        (
            "RS_AVG_1.5m",
            "W/m2",
            SensorDeviceClass.IRRADIANCE,
            UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        ),
        (
            "VV_AVG_10m",
            "m/s",
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.METERS_PER_SECOND,
        ),
    ]

    for code, unit, device_class, native_unit in cases:
        description = _station_measure_description(
            _measure(code, code, unit), "last_10_min"
        )
        assert description.device_class == device_class
        assert description.native_unit_of_measurement == native_unit

    total = _station_measure_description(
        _measure("PP_SUM_1.5m", "Chuvia", "L/m2"), "daily"
    )
    assert total.state_class == SensorStateClass.TOTAL
    assert total.translation_key == "station_measure_daily"


def test_station_measure_entities_are_stable_and_follow_updates():
    payload = {
        "listUltimos10min": [
            {
                "estacion": "Santiago-EOAS",
                "listaMedidas": [
                    _measure("TA_AVG_1.5m", "Temperatura", "ºC", 20.5),
                    _measure("HR_AVG_1.5m", "Humidade", "%", -9999, 9),
                ],
            }
        ]
    }
    coordinator = SimpleNamespace(data=payload, last_update_success=True)

    entities = _station_measure_entities("10124", coordinator, "last_10_min")

    assert len(entities) == 2
    assert entities[0].unique_id == (
        "meteogalicia_station_10124_last_10_min_TA_AVG_1.5m"
    )
    assert entities[0].native_value == 20.5
    assert entities[0].available is True
    assert entities[1].native_value is None
    assert entities[1].available is False

    payload["listUltimos10min"][0]["listaMedidas"][0]["valor"] = 21.0
    assert entities[0].native_value == 21.0


def test_duplicate_measure_codes_create_only_one_entity():
    duplicate = _measure("TA_AVG_1.5m", "Temperatura", "ºC")
    coordinator = SimpleNamespace(
        data={
            "listDatosDiarios": [
                {
                    "listaEstacions": [
                        {
                            "estacion": "Santiago-EOAS",
                            "listaMedidas": [duplicate, duplicate],
                        }
                    ]
                }
            ]
        },
        last_update_success=True,
    )

    assert len(_station_measure_entities("10124", coordinator, "daily")) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("config,legacy,expected,measure_count", [
    ({}, None, [3600, 600], 2),
    ({}, 1800, [1800, 1800], 2),
    ({"station_daily_interval": 7200, "observation_interval": 900}, 15, [7200, 900], 2),
    ({"scan_interval": 15, "station_daily_interval": None}, None, [3600, 15], 2),
    ({const.CONF_ID_ESTACION_MEDIDA_DAILY: "TA_AVG_1.5m"}, None, [3600], 0),
    ({const.CONF_ID_ESTACION_MEDIDA_LAST10MIN: "HR_AVG_1.5m"}, None, [600], 0),
])
async def test_station_setup_keeps_legacy_summaries_and_adds_measure_entities(
    monkeypatch, config, legacy, expected, measure_count,
):
    daily_payload = {
        "listDatosDiarios": [
            {
                "listaEstacions": [
                    {
                        "estacion": "Santiago-EOAS",
                        "listaMedidas": [
                            _measure("TA_AVG_1.5m", "Temperatura", "ºC", 20.5)
                        ],
                    }
                ]
            }
        ]
    }
    last_10_payload = {
        "listUltimos10min": [
            {
                "estacion": "Santiago-EOAS",
                "listaMedidas": [_measure("HR_AVG_1.5m", "Humidade", "%", 70)],
            }
        ]
    }

    intervals = []

    class FakeCoordinator:
        payload = None

        def __init__(self, _hass, _station_id, _scan_interval):
            intervals.append(_scan_interval)
            self.data = self.payload
            self.last_update_success = True
            self.last_api_connected_at = None
            self.last_api_latency_ms = None
            self.update_interval = None

        async def async_refresh(self):
            return None

        def async_set_updated_data(self, data):
            self.data = data

    class DailyCoordinator(FakeCoordinator):
        payload = daily_payload

    class Last10Coordinator(FakeCoordinator):
        payload = last_10_payload

    from custom_components.meteogalicia import sensor

    monkeypatch.setattr(sensor, "MeteoGaliciaStationDailyCoordinator", DailyCoordinator)
    monkeypatch.setattr(
        sensor, "MeteoGaliciaStationLast10MinCoordinator", Last10Coordinator
    )
    added = []

    coordinators = []
    await setup_id_estacion_platform(
        "10124", config, added.extend, object(), legacy, coordinators
    )

    assert intervals == expected
    assert len(coordinators) == len(expected)
    assert len(added) == len(expected) + measure_count
    assert (
        sum(
            entity.__class__.__name__ == "MeteoGaliciaStationMeasureSensor"
            for entity in added
        )
        == measure_count
    )
