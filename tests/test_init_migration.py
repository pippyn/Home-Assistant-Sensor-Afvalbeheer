"""Tests for the config entry migration logic in __init__.py.

Exercises _check_if_migration_needed, _migrate_entry_to_v3 and
_migrate_entry_to_v3_2 against the real entity registry (via MockConfigEntry
and the `hass` fixture), since this is the most fragile, previously-untested
part of the integration (see AGENTS.md note on unique_id migration).
"""
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.afvalbeheer import (
    _check_if_migration_needed,
    _migrate_entry_to_v3,
    _migrate_entry_to_v3_2,
    async_migrate_entry,
)
from custom_components.afvalbeheer.const import (
    CONF_POSTCODE,
    CONF_RESOURCES,
    CONF_STREET_NUMBER,
    CONF_WASTE_COLLECTOR,
    DOMAIN,
)
from custom_components.afvalbeheer.sensor import _format_unique_id


def _make_entry(hass, waste_collector, version=1, minor_version=1, resources=None):
    data = {
        CONF_WASTE_COLLECTOR: waste_collector,
        CONF_POSTCODE: "1234AB",
        CONF_STREET_NUMBER: "1",
    }
    if resources is not None:
        data[CONF_RESOURCES] = resources
    entry = MockConfigEntry(domain=DOMAIN, version=version, minor_version=minor_version, data=data)
    entry.add_to_hass(hass)
    return entry


# --- _check_if_migration_needed ---------------------------------------------


async def test_check_migration_needed_detects_old_unique_id_format(hass):
    entry = _make_entry(hass, "mijnafvalwijzer")
    registry = er.async_get(hass)
    # Old format: unique_id prefixed with the entry_id itself.
    registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_restafval", config_entry=entry
    )

    assert _check_if_migration_needed(hass, entry) is True


async def test_check_migration_not_needed_for_new_format(hass):
    entry = _make_entry(hass, "demo", version=3, minor_version=2)
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, "restafval", config_entry=entry)

    assert _check_if_migration_needed(hass, entry) is False


async def test_check_migration_ignores_entities_from_other_entries(hass):
    entry = _make_entry(hass, "demo")
    other_entry = _make_entry(hass, "demo")
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor", DOMAIN, f"{other_entry.entry_id}_restafval", config_entry=other_entry
    )

    assert _check_if_migration_needed(hass, entry) is False


# --- _migrate_entry_to_v3 ----------------------------------------------------


async def test_migrate_to_v3_rewrites_old_unique_id_and_bumps_version(hass):
    entry = _make_entry(hass, "mijnafvalwijzer")
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_restafval", config_entry=entry
    )

    assert await _migrate_entry_to_v3(hass, entry) is True

    updated = registry.async_get(entity.entity_id)
    assert updated.unique_id == "restafval"
    assert entry.version == 3
    assert entry.minor_version == 1


async def test_migrate_to_v3_includes_custom_name_for_uniqueness(hass):
    entry = _make_entry(hass, "mijnafvalwijzer")
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={**entry.data, "name": "Mijn Container"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_restafval", config_entry=entry
    )

    assert await _migrate_entry_to_v3(hass, entry) is True

    updated = registry.async_get(entity.entity_id)
    # _format_unique_id puts the sensor type first, then the custom name, when
    # there is no collector-prefix condition (see sensor.py: parts.insert(1, name)).
    assert updated.unique_id == "restafval_mijn_container"


async def test_migrate_to_v3_leaves_already_correct_unique_id_unchanged(hass):
    entry = _make_entry(hass, "demo")
    registry = er.async_get(hass)
    entity = registry.async_get_or_create("sensor", DOMAIN, "restafval", config_entry=entry)

    assert await _migrate_entry_to_v3(hass, entry) is True

    updated = registry.async_get(entity.entity_id)
    assert updated.unique_id == "restafval"
    assert entry.version == 3
    assert entry.minor_version == 1


# --- _migrate_entry_to_v3_2 ---------------------------------------------------


async def test_migrate_to_v3_2_prefixes_cleanprofs_resources_and_unique_ids(hass):
    entry = _make_entry(hass, "cleanprofs", version=3, minor_version=1, resources=["gft", "Reiniging Restafval"])
    registry = er.async_get(hass)
    old_unique_id = _format_unique_id(None, False, "cleanprofs", "gft", entry.entry_id).lower()
    entity = registry.async_get_or_create("sensor", DOMAIN, old_unique_id, config_entry=entry)

    assert await _migrate_entry_to_v3_2(hass, entry) is True

    updated = registry.async_get(entity.entity_id)
    assert updated.unique_id == "cleanprofs_reiniging_gft"
    # Already-prefixed resources are left untouched; unprefixed ones get prefixed.
    assert entry.data[CONF_RESOURCES] == ["Reiniging gft", "Reiniging Restafval"]
    assert entry.version == 3
    assert entry.minor_version == 2


async def test_migrate_to_v3_2_is_noop_for_non_cleanprofs_collector(hass):
    entry = _make_entry(hass, "demo", version=3, minor_version=1)

    assert await _migrate_entry_to_v3_2(hass, entry) is True

    assert entry.version == 3
    assert entry.minor_version == 2


async def test_migrate_to_v3_2_skips_unique_id_already_in_use(hass):
    entry = _make_entry(hass, "cleanprofs", version=3, minor_version=1, resources=["gft"])
    registry = er.async_get(hass)
    old_id = _format_unique_id(None, False, "cleanprofs", "gft", entry.entry_id).lower()
    new_id = _format_unique_id(None, False, "cleanprofs", "Reiniging gft", entry.entry_id).lower()
    old_entity = registry.async_get_or_create("sensor", DOMAIN, old_id, config_entry=entry)
    registry.async_get_or_create("sensor", DOMAIN, new_id, config_entry=entry)

    assert await _migrate_entry_to_v3_2(hass, entry) is True

    # The colliding entity is left on its old unique_id rather than overwritten.
    assert registry.async_get(old_entity.entity_id).unique_id == old_id
    # The resource list is still updated even though the entity migration was skipped.
    assert entry.data[CONF_RESOURCES] == ["Reiniging gft"]


# --- async_migrate_entry (dispatcher) ----------------------------------------


async def test_async_migrate_entry_runs_both_steps_from_v1(hass):
    entry = _make_entry(hass, "cleanprofs", version=1, minor_version=1, resources=["gft"])
    registry = er.async_get(hass)
    old_unique_id = f"{entry.entry_id}_gft"
    entity = registry.async_get_or_create("sensor", DOMAIN, old_unique_id, config_entry=entry)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    assert entry.minor_version == 2
    updated = registry.async_get(entity.entity_id)
    assert updated.unique_id == "cleanprofs_reiniging_gft"
    assert entry.data[CONF_RESOURCES] == ["Reiniging gft"]


async def test_async_migrate_entry_is_noop_when_already_current(hass):
    entry = _make_entry(hass, "demo", version=3, minor_version=2)
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, "restafval", config_entry=entry)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    assert entry.minor_version == 2
