"""Tests for built-in icon mappings."""
import base64
import re
from pathlib import Path

from custom_components.afvalbeheer.const import FRACTION_ICONS_NEW, FRACTION_ICONS_NEW_BOLD

DATA_URI_PREFIX = "data:image/svg+xml;base64,"


def _decode_svg(data_uri):
    assert data_uri.startswith(DATA_URI_PREFIX)
    return base64.b64decode(data_uri.removeprefix(DATA_URI_PREFIX)).decode()


def test_restafvalzakken_has_own_modern_icon():
    assert FRACTION_ICONS_NEW["restafvalzakken"] != FRACTION_ICONS_NEW["restafval"]

    svg = _decode_svg(FRACTION_ICONS_NEW["restafvalzakken"])
    assert 'id="afvalbeheer-restafvalzakken"' in svg
    assert "afvalbeheer-restafval" not in svg.replace("afvalbeheer-restafvalzakken", "")
    assert 'fill="none"' in svg
    assert 'stroke="#1B1D3B"' in svg
    assert 'stroke="#FFFFFF"' not in svg


def test_restafvalzakken_has_own_bold_modern_icon():
    assert FRACTION_ICONS_NEW_BOLD["restafvalzakken"] != FRACTION_ICONS_NEW_BOLD["restafval"]

    svg = _decode_svg(FRACTION_ICONS_NEW_BOLD["restafvalzakken"])
    assert 'id="afvalbeheer-restafvalzakken-bold"' in svg
    assert 'fill="none"' in svg
    assert 'stroke="#1B1D3B"' in svg
    assert 'stroke="#FFFFFF"' not in svg


def test_restafvalzakken_is_registered_for_theme_switching():
    js = Path("custom_components/afvalbeheer/frontend/afvalbeheer-icons.js").read_text()

    assert "RESTAFVALZAKKEN_DARK" in js
    assert "RESTAFVALZAKKEN_LIGHT" in js
    assert "restafvalzakken: { regular:" in js
    assert "restafvalzakken|restafval" in js

    dark_svg = base64.b64decode(re.search(r'RESTAFVALZAKKEN_DARK = "([A-Za-z0-9+/=]+)"', js).group(1)).decode()
    light_svg = base64.b64decode(re.search(r'RESTAFVALZAKKEN_LIGHT = "([A-Za-z0-9+/=]+)"', js).group(1)).decode()
    assert 'fill="none"' in dark_svg
    assert 'fill="none"' in light_svg
    assert 'stroke="#FFFFFF"' in dark_svg
    assert 'stroke="#1B1D3B"' in light_svg
