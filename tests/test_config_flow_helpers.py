"""Tests for the pure helper functions in config_flow.py.

These do not require a running Home Assistant instance since they operate
only on plain dicts.
"""
from custom_components.afvalbeheer.config_flow import (
    _apply_icon_set,
    _default_language,
    _icon_set_from_config,
    RESOURCES_ERROR_MAP,
)
from custom_components.afvalbeheer.const import (
    CONF_BOLD_ICONS,
    CONF_BUILT_IN_ICONS,
    CONF_BUILT_IN_ICONS_NEW,
    CONF_DISABLE_ICONS,
    CONF_ICON_SET,
    CONF_LANGUAGE,
    CONF_TRANSLATE_DAYS,
    ICON_SET_CLASSIC,
    ICON_SET_CLASSIC_BOLD,
    ICON_SET_DEFAULT,
    ICON_SET_MODERN,
    ICON_SET_MODERN_BOLD,
    LANGUAGE_EN,
    LANGUAGE_NL,
)


def test_default_language_uses_explicit_language():
    assert _default_language({CONF_LANGUAGE: "fr"}) == "fr"


def test_default_language_falls_back_to_translate_days():
    assert _default_language({CONF_TRANSLATE_DAYS: True}) == LANGUAGE_NL
    assert _default_language({CONF_TRANSLATE_DAYS: False}) == LANGUAGE_EN
    # DEFAULT_CONFIG[CONF_TRANSLATE_DAYS] defaults to True, so an empty config
    # falls back to Dutch, matching _default_language's own default behaviour.
    assert _default_language({}) == LANGUAGE_NL


def test_icon_set_from_config_disabled_takes_precedence():
    config = {CONF_DISABLE_ICONS: True, CONF_BUILT_IN_ICONS_NEW: True}
    assert _icon_set_from_config(config) == ICON_SET_DEFAULT


def test_icon_set_from_config_modern_variants():
    assert _icon_set_from_config({CONF_BUILT_IN_ICONS_NEW: True}) == ICON_SET_MODERN
    assert _icon_set_from_config(
        {CONF_BUILT_IN_ICONS_NEW: True, CONF_BOLD_ICONS: True}
    ) == ICON_SET_MODERN_BOLD


def test_icon_set_from_config_classic_variants():
    assert _icon_set_from_config({CONF_BUILT_IN_ICONS: True}) == ICON_SET_CLASSIC
    assert _icon_set_from_config(
        {CONF_BUILT_IN_ICONS: True, CONF_BOLD_ICONS: True}
    ) == ICON_SET_CLASSIC_BOLD


def test_icon_set_from_config_default_when_nothing_set():
    assert _icon_set_from_config({}) == ICON_SET_DEFAULT


def test_apply_icon_set_modern_bold():
    data = {CONF_ICON_SET: ICON_SET_MODERN_BOLD}
    _apply_icon_set(data)
    assert data[CONF_BUILT_IN_ICONS] is False
    assert data[CONF_BUILT_IN_ICONS_NEW] is True
    assert data[CONF_BOLD_ICONS] is True
    assert data[CONF_DISABLE_ICONS] is False
    assert CONF_ICON_SET not in data


def test_apply_icon_set_default_disables_icons():
    data = {CONF_ICON_SET: ICON_SET_DEFAULT}
    _apply_icon_set(data)
    assert data[CONF_BUILT_IN_ICONS] is False
    assert data[CONF_BUILT_IN_ICONS_NEW] is False
    assert data[CONF_BOLD_ICONS] is False
    assert data[CONF_DISABLE_ICONS] is False


def test_apply_icon_set_noop_when_missing():
    data = {"other_key": "value"}
    _apply_icon_set(data)
    assert data == {"other_key": "value"}


def test_resources_error_map_covers_known_errors():
    for key in ("import_failed", "no_data", "invalid_data", "no_resources", "api_error"):
        assert key in RESOURCES_ERROR_MAP
