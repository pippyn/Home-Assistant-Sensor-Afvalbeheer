"""Integration test for WasteData using the built-in demo collector.

Uses the real `hass` fixture from pytest-homeassistant-custom-component to
exercise get_wastedata_from_config() and WasteData end-to-end, without any
network access, via the "demo" collector.
"""
from custom_components.afvalbeheer.API import get_wastedata_from_config
from custom_components.afvalbeheer.const import (
    CONF_CUSTOM_MAPPING,
    CONF_CUSTOMER_ID,
    CONF_POSTCODE,
    CONF_PRINT_AVAILABLE_WASTE_TYPES,
    CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS,
    CONF_RESOURCES,
    CONF_STREET_NUMBER,
    CONF_UPDATE_INTERVAL,
    CONF_WASTE_COLLECTOR,
)


def _demo_config():
    return {
        CONF_WASTE_COLLECTOR: "demo",
        CONF_POSTCODE: "1234AB",
        CONF_STREET_NUMBER: "1",
        CONF_RESOURCES: ["restafval"],
        CONF_CUSTOM_MAPPING: {},
        CONF_PRINT_AVAILABLE_WASTE_TYPES: False,
        CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS: False,
        CONF_UPDATE_INTERVAL: 0,
        CONF_CUSTOMER_ID: "",
    }


async def test_get_wastedata_from_config_selects_demo_collector(hass):
    data = get_wastedata_from_config(hass, _demo_config())
    assert data is not None
    assert data.collector is not None
    assert data.collector.__class__.__name__ == "DemoCollector"


async def test_demo_collector_update_produces_collections(hass):
    data = get_wastedata_from_config(hass, _demo_config())
    await data.collector.update()
    available = data.collections.get_available_waste_types()
    assert len(available) > 0


async def test_demo_collector_has_upcoming_collections(hass):
    data = get_wastedata_from_config(hass, _demo_config())
    await data.collector.update()
    upcoming = data.collections.get_upcoming()
    assert len(upcoming) > 0
    assert all(c.date is not None for c in upcoming)
