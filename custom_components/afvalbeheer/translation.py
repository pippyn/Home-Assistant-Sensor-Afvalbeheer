"""Translation helpers for integration-controlled runtime text."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from .const import (
    CONF_LANGUAGE,
    CONF_TRANSLATE_DAYS,
    LANGUAGE_EN,
    LANGUAGE_NL,
    SUPPORTED_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)

_RUNTIME_KEY = "runtime"
_DEFAULT_LANGUAGE = LANGUAGE_NL


def resolve_language(config):
    """Resolve the configured integration language.

    Keeps the previous `dutch` boolean working for existing YAML/config entries.
    """
    language = config.get(CONF_LANGUAGE)
    if language in SUPPORTED_LANGUAGES:
        return language

    return LANGUAGE_NL if config.get(CONF_TRANSLATE_DAYS) else LANGUAGE_EN


async def async_prepare_translations(hass, language):
    """Preload runtime translation files outside Home Assistant's event loop.

    The sync helpers below are used while entities are created/updated. Preloading
    the selected language and the Dutch fallback through the executor prevents
    blocking file I/O warnings when those helpers are called from the event loop.
    """
    await hass.async_add_executor_job(_load_translations, language)

    if language != _DEFAULT_LANGUAGE:
        await hass.async_add_executor_job(_load_translations, _DEFAULT_LANGUAGE)


@lru_cache(maxsize=None)
def _load_translations(language):
    """Load a translation JSON file from translations/<language>.json."""
    path = Path(__file__).parent / "translations" / f"{language}.json"

    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        _LOGGER.warning("Translation file not found for language %s", language)
        return {}
    except json.JSONDecodeError as err:
        _LOGGER.error("Invalid translation JSON for language %s: %s", language, err)
        return {}


def _get_nested(data, key):
    """Return a nested dictionary value using dot notation."""
    value = data
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
        if value is None:
            return None
    return value


def text(language, key, **kwargs):
    """Return translated integration runtime text with Dutch fallback."""
    full_key = f"{_RUNTIME_KEY}.{key}"
    value = _get_nested(_load_translations(language), full_key)

    if value is None and language != _DEFAULT_LANGUAGE:
        value = _get_nested(_load_translations(_DEFAULT_LANGUAGE), full_key)

    if value is None:
        _LOGGER.warning("Missing runtime translation key %s for language %s", full_key, language)
        return key

    return value.format(**kwargs) if kwargs else value


def translate_date_text(language, value):
    """Translate day and month names in a formatted date string."""
    runtime_translations = _get_nested(_load_translations(language), _RUNTIME_KEY)

    if runtime_translations is None and language != _DEFAULT_LANGUAGE:
        runtime_translations = _get_nested(_load_translations(_DEFAULT_LANGUAGE), _RUNTIME_KEY)

    if not runtime_translations:
        return value

    for section in ("months", "months_short", "days", "days_short"):
        translations = runtime_translations.get(section, {})
        for source, target in translations.items():
            value = value.replace(source, target)

    return value
