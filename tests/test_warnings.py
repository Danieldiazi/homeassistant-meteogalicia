"""Tests for MeteoGalicia weather warning helpers."""

from custom_components.meteogalicia.binary_sensor import _warning_items
from custom_components.meteogalicia.sensor import _WARNING_LEVEL_NAMES


def test_warning_items_preserve_detailed_payload():
    warning = {
        "idNivel": 2,
        "tipoalerta_es": "Viento",
        "dataIni": "2026-09-27T06:00:00",
        "dataFin": "2026-09-27T18:00:00",
    }

    assert _warning_items({"listaAvisosConcellos": [warning]}) == [warning]


def test_warning_items_ignore_invalid_payload():
    assert _warning_items(None) == []
    assert _warning_items({}) == []
    assert _warning_items({"listaAvisosConcellos": None}) == []
    assert _warning_items({"listaAvisosConcellos": ["bad", {"idNivel": 1}]}) == [
        {"idNivel": 1}
    ]


def test_warning_level_names_match_meteogalicia_scale():
    assert _WARNING_LEVEL_NAMES == {
        0: "normal",
        1: "yellow",
        2: "orange",
        3: "red",
    }
