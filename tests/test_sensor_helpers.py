"""Tests for the pure helper functions in sensor.py."""
from custom_components.afvalbeheer.sensor import (
    _fraction_icon_keys,
    _format_sensor,
    _format_unique_id,
)


def test_format_sensor_without_prefix_when_name_matches_collector():
    assert _format_sensor("Mijnafvalwijzer", False, "Mijnafvalwijzer", "Papier") == "Papier"


def test_format_sensor_adds_prefix_when_name_differs():
    assert _format_sensor("Home", False, "Mijnafvalwijzer", "Papier") == "Home Papier"


def test_format_sensor_with_empty_name():
    assert _format_sensor("", False, "Mijnafvalwijzer", "Papier") == "Papier"


def test_fraction_icon_keys_strips_reiniging_prefix():
    key, lower = _fraction_icon_keys("Reiniging GFT")
    assert key == "gft"
    assert lower == "gft"


def test_fraction_icon_keys_replaces_spaces_and_underscores():
    key, lower = _fraction_icon_keys("Grof Afval_Hout")
    assert key == "grof-afval-hout"
    assert lower == "grof afval_hout"


def test_fraction_icon_keys_without_reiniging_prefix():
    key, lower = _fraction_icon_keys("Papier")
    assert key == "papier"
    assert lower == "papier"


def test_format_unique_id_basic():
    unique_id = _format_unique_id(
        name="Mijnafvalwijzer",
        name_prefix=False,
        waste_collector="Mijnafvalwijzer",
        sensor_type="Papier",
        entry_id="abc123",
    )
    assert unique_id == "papier"


def test_format_unique_id_adds_collector_prefix_for_cleanprofs():
    unique_id = _format_unique_id(
        name="Cleanprofs",
        name_prefix=False,
        waste_collector="cleanprofs",
        sensor_type="Container",
        entry_id="abc123",
    )
    assert unique_id.startswith("cleanprofs_")


def test_format_unique_id_adds_name_prefix_when_name_differs():
    unique_id = _format_unique_id(
        name="Thuis",
        name_prefix=True,
        waste_collector="Mijnafvalwijzer",
        sensor_type="Papier",
        entry_id="abc123",
    )
    assert unique_id == "mijnafvalwijzer_thuis_papier"


def test_format_unique_id_lowercases_and_strips_separators():
    unique_id = _format_unique_id(
        name="My Address-1",
        name_prefix=True,
        waste_collector="ROVA",
        sensor_type="Papier",
        entry_id="abc123",
    )
    assert unique_id == "rova_my_address_1_papier"
