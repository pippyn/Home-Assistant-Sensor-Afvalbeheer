"""Config flow and options flow tests for the Custom collector."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.afvalbeheer.const import (
    CONF_BUILT_IN_ICONS_NEW,
    CONF_CUSTOM_DATES,
    CONF_CUSTOM_WASTE_TYPE,
    CONF_ICON_SET,
    CONF_ID,
    CONF_NAME_PREFIX,
    CONF_RESOURCES,
    CONF_WASTE_COLLECTOR,
    DEFAULT_CONFIG,
    DOMAIN,
    ICON_SET_MODERN,
)


async def _start_custom_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_WASTE_COLLECTOR: "Overig"})


def _custom_entry(**overrides):
    data = {
        **DEFAULT_CONFIG,
        CONF_WASTE_COLLECTOR: "Overig",
        CONF_NAME: "Thuis",
        CONF_NAME_PREFIX: True,
        CONF_CUSTOM_WASTE_TYPE: "GFT",
        CONF_CUSTOM_DATES: ["2030-01-01", "2030-01-15"],
        CONF_RESOURCES: ["GFT"],
        CONF_ID: "entry-uuid",
    }
    data.update(overrides)
    return MockConfigEntry(domain=DOMAIN, version=3, minor_version=2, title="Overig - Thuis (GFT)", data=data)


async def test_setup_flow_creates_custom_entry(hass):
    result = await _start_custom_flow(hass)
    assert result["step_id"] == "custom"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Thuis", CONF_CUSTOM_WASTE_TYPE: "GFT"}
    )
    assert result["step_id"] == "custom_dates"

    # Each submitted date re-shows the step; duplicates are dropped
    for new_date in ("2030-01-15", "2030-01-01", "2030-01-15"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"date": new_date})
        assert result["step_id"] == "custom_dates"

    # Submitting without a new date moves on
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-01", "2030-01-15"]}
    )
    assert result["step_id"] == "custom_options"

    with patch("custom_components.afvalbeheer.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ICON_SET: ICON_SET_MODERN})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overig - Thuis (GFT)"
    data = result["data"]
    assert data[CONF_CUSTOM_DATES] == ["2030-01-01", "2030-01-15"]
    assert data[CONF_RESOURCES] == ["GFT"]
    assert data[CONF_BUILT_IN_ICONS_NEW] is True
    assert CONF_ICON_SET not in data
    assert data[CONF_ID]


async def test_setup_flow_requires_a_name(hass):
    result = await _start_custom_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "   ", CONF_CUSTOM_WASTE_TYPE: "GFT"}
    )
    assert result["step_id"] == "custom"
    assert result["errors"] == {"base": "name_required"}


async def test_dates_step_requires_at_least_one_date(hass):
    result = await _start_custom_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Thuis", CONF_CUSTOM_WASTE_TYPE: "GFT"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "custom_dates"
    assert result["errors"] == {"base": "no_dates"}


async def test_dates_step_unchecking_removes_a_date(hass):
    result = await _start_custom_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Thuis", CONF_CUSTOM_WASTE_TYPE: "GFT"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"date": "2030-01-01"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-01"], "date": "2030-01-15"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-15"]})
    assert result["step_id"] == "custom_options"

    with patch("custom_components.afvalbeheer.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["data"][CONF_CUSTOM_DATES] == ["2030-01-15"]


async def test_options_flow_edits_dates_and_keeps_name(hass):
    entry = _custom_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_WASTE_COLLECTOR: "Overig"})
    assert result["step_id"] == "custom"
    # The name is part of the unique_ids, so it is not offered again
    assert CONF_NAME not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_CUSTOM_WASTE_TYPE: "GFT"})
    assert result["step_id"] == "custom_dates"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-15"], "date": "2030-02-01"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-15", "2030-02-01"]}
    )
    assert result["step_id"] == "custom_options"
    assert CONF_NAME_PREFIX not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_NAME] == "Thuis"
    assert entry.options[CONF_CUSTOM_DATES] == ["2030-01-15", "2030-02-01"]


async def test_options_flow_waste_type_change_removes_old_sensor(hass):
    entry = _custom_entry()
    entry.add_to_hass(hass)
    # Set the entry up for real: the options flow reloads it, and that reload must not
    # bring back the sensor of the previous waste type
    with patch("custom_components.afvalbeheer._async_register_frontend"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        assert entity_registry.async_get_entity_id("sensor", DOMAIN, "overig_thuis_gft")

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_WASTE_COLLECTOR: "Overig"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_CUSTOM_WASTE_TYPE: "PMD"})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-01", "2030-01-15"]}
        )
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RESOURCES] == ["PMD"]
    assert entry.title == "Overig - Thuis (PMD)"
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "overig_thuis_gft") is None
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "overig_thuis_pmd")


async def test_yaml_import_keeps_custom_dates_and_waste_type(hass):
    yaml_config = {
        CONF_WASTE_COLLECTOR: "overig",
        "postcode": "1111AA",
        "streetnumber": "1",
        CONF_RESOURCES: [],
        CONF_NAME: "Volkstuin",
        CONF_CUSTOM_WASTE_TYPE: "Papier",
        CONF_CUSTOM_DATES: ["2030-03-01", "2030-02-01"],
    }
    with patch("custom_components.afvalbeheer.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=yaml_config
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CUSTOM_WASTE_TYPE] == "Papier"
    assert result["data"][CONF_CUSTOM_DATES] == ["2030-02-01", "2030-03-01"]
    assert result["data"][CONF_RESOURCES] == ["Papier"]


async def test_collector_dropdown_lists_overig_last_with_translated_label(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    config = result["data_schema"].schema[CONF_WASTE_COLLECTOR].config
    assert config["options"][-1] == "Overig"
    assert config["translation_key"] == CONF_WASTE_COLLECTOR


def test_collector_label_is_translated_per_language():
    import json
    from pathlib import Path

    translations = Path(__file__).parent.parent / "custom_components" / "afvalbeheer" / "translations"
    labels = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))["selector"][CONF_WASTE_COLLECTOR]["options"]["Overig"]
        for path in translations.glob("*.json")
    }
    assert labels == {"nl": "Overig", "en": "Other", "fr": "Autre", "de": "Sonstige", "el": "Άλλο"}


async def test_dates_step_add_another_off_adds_date_and_continues(hass):
    result = await _start_custom_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Thuis", CONF_CUSTOM_WASTE_TYPE: "GFT"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"date": "2030-01-01", "add_another": True}
    )
    assert result["step_id"] == "custom_dates"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CUSTOM_DATES: ["2030-01-01"], "date": "2030-01-15", "add_another": False}
    )
    assert result["step_id"] == "custom_options"

    with patch("custom_components.afvalbeheer.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["data"][CONF_CUSTOM_DATES] == ["2030-01-01", "2030-01-15"]
