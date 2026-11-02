"""Regression tests for DeAfvalApp address transport security."""
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from custom_components.afvalbeheer.collectors.individual.deafvalapp import DeAfvalAppCollector
from custom_components.afvalbeheer.const import DEFAULT_REQUEST_TIMEOUT


async def test_deafvalapp_uses_verified_https_without_redirects(hass):
    """Send address data only to the HTTPS endpoint with default TLS verification."""
    collector = DeAfvalAppCollector(hass, "deafvalapp", "1234AB", "1", "A", {})
    response = Mock(status_code=200, text="rest;01-01-2099;")
    with patch("requests.get", return_value=response) as get:
        await collector.update()

    url = urlsplit(get.call_args.args[0])
    assert url.scheme == "https"
    assert url.netloc == "dataservice.deafvalapp.nl"
    assert parse_qs(url.query)["postcode"] == ["1234AB"]
    assert parse_qs(url.query)["huisnr"] == ["1"]
    assert get.call_args.kwargs == {
        "timeout": DEFAULT_REQUEST_TIMEOUT, "allow_redirects": False,
    }
    response.raise_for_status.assert_called_once_with()
    assert len(collector.collections) == 1


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 500])
async def test_deafvalapp_rejects_redirects_and_http_errors(hass, status):
    """Do not follow redirects or parse failed responses as collection data."""
    collector = DeAfvalAppCollector(hass, "deafvalapp", "1234AB", "1", "", {})
    response = Mock(status_code=status, text="rest;01-01-2099;")
    response.headers = {"Location": "http://dataservice.deafvalapp.nl/"}
    if status == 500:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError("failed")
    with patch("requests.get", return_value=response) as get:
        assert await collector.update() is False

    get.assert_called_once()
    assert get.call_args.kwargs["allow_redirects"] is False
    assert len(collector.collections) == 0


async def test_deafvalapp_does_not_fall_back_after_tls_failure(hass):
    """A TLS failure must not trigger a retry over HTTP."""
    collector = DeAfvalAppCollector(hass, "deafvalapp", "1234AB", "1", "", {})
    with patch("requests.get", side_effect=requests.exceptions.SSLError("invalid certificate")) as get:
        assert await collector.update() is False

    get.assert_called_once()
    assert get.call_args.args[0].startswith("https://")

