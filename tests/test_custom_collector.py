"""Tests for the Custom collector with manually entered collection dates.

Uses the real `hass` fixture from pytest-homeassistant-custom-component to
exercise get_wastedata_from_config() and WasteData end-to-end.
"""
from datetime import date, datetime

from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.collectors.individual.custom import normalize_custom_dates
from custom_components.afvalbeheer.config_flow import (
    _custom_options_defaults,
    _is_custom_collector,
)
from custom_components.afvalbeheer.const import (
    CONF_CUSTOM_DATES,
    CONF_CUSTOM_MAPPING,
    CONF_CUSTOM_WASTE_TYPE,
    CONF_ICON_SET,
    CONF_ID,
    CONF_POSTCODE,
    CONF_RESOURCES,
    CONF_STREET_NUMBER,
    CONF_WASTE_COLLECTOR,
    ICON_SET_MODERN,
)


def _custom_config(**overrides):
    config = {
        CONF_WASTE_COLLECTOR: "Overig",
        CONF_POSTCODE: "",
        CONF_STREET_NUMBER: "",
        CONF_RESOURCES: ["GFT"],
        CONF_CUSTOM_MAPPING: {},
        CONF_CUSTOM_WASTE_TYPE: "GFT",
        CONF_CUSTOM_DATES: ["2030-01-15", "2030-01-01"],
    }
    config.update(overrides)
    return config


def test_normalize_custom_dates_sorts_dedupes_and_skips_invalid():
    dates = ["2030-01-15", "2030-01-01", "2030-01-15", "not-a-date", date(2030, 2, 1), datetime(2030, 3, 1, 12)]
    assert normalize_custom_dates(dates) == ["2030-01-01", "2030-01-15", "2030-02-01", "2030-03-01"]


def test_normalize_custom_dates_handles_none():
    assert normalize_custom_dates(None) == []


async def test_get_wastedata_from_config_selects_custom_collector(hass):
    data = get_wastedata_from_config(hass, _custom_config())
    assert data is not None
    assert data.collector.__class__.__name__ == "CustomCollector"


async def test_custom_collector_update_loads_dates(hass):
    data = get_wastedata_from_config(hass, _custom_config())
    await data.collector.update()
    collections = data.collections.get_sorted()
    assert [c.date for c in collections] == [datetime(2030, 1, 1), datetime(2030, 1, 15)]
    assert all(c.waste_type == "GFT" for c in collections)
    assert data.collections.get_available_waste_types() == ["GFT"]


async def test_custom_collector_without_waste_type_loads_nothing(hass):
    data = get_wastedata_from_config(hass, _custom_config(**{CONF_CUSTOM_WASTE_TYPE: None}))
    await data.collector.update()
    assert data.collections.get_sorted() == []


async def test_custom_entries_keep_their_own_id(hass):
    first = _custom_config(**{CONF_ID: "entry-one"})
    second = _custom_config(**{CONF_ID: "entry-two"})
    get_wastedata_from_config(hass, first)
    get_wastedata_from_config(hass, second)
    assert first[CONF_ID] != second[CONF_ID]


def test_is_custom_collector_is_case_insensitive():
    assert _is_custom_collector("Overig")
    assert _is_custom_collector("overig")
    assert not _is_custom_collector("Demo")
    assert not _is_custom_collector(None)


def test_custom_options_defaults_for_new_entry_use_modern_icons():
    assert _custom_options_defaults({})[CONF_ICON_SET] == ICON_SET_MODERN
