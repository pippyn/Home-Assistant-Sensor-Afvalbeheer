"""Regression coverage for bundled runtime translations outside HA's schema."""
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.afvalbeheer.translation import (
    _load_translations,
    async_prepare_translations,
    text,
    translate_date_text,
)


@pytest.mark.parametrize('language, today', [
    ('nl', 'Vandaag'), ('en', 'Today'), ('fr', "Aujourd'hui"),
    ('de', 'Heute'), ('el', 'Σήμερα'),
])
def test_runtime_text_uses_bundled_language_files(language, today):
    _load_translations.cache_clear()
    assert text(language, 'today') == today
    assert 'synthetic' in text(language, 'notifications.city_required', collector='synthetic')


def test_runtime_text_and_date_names_fall_back_to_dutch():
    assert text('unknown-language', 'today') == 'Vandaag'
    assert translate_date_text('unknown-language', 'Monday January') == 'Maandag januari'
    assert translate_date_text('fr', 'Monday January') == 'Lundi janvier'


async def test_runtime_translations_are_preloaded_outside_event_loop(hass):
    _load_translations.cache_clear()
    await async_prepare_translations(hass, 'fr')
    with patch.object(Path, 'open', side_effect=AssertionError('Unexpected file I/O')):
        assert text('fr', 'tomorrow') == 'Demain'
        assert text('nl', 'none') == 'Geen'
    _load_translations.cache_clear()
