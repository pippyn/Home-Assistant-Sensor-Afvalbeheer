"""
AfvalhulpCollector for waste data from Afvalhulp.nl
"""

import logging
from datetime import datetime
import asyncio
import requests
import re

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_GREEN, WASTE_TYPE_PAPER, WASTE_TYPE_PMD_GREY

_LOGGER = logging.getLogger(__name__)


class AfvalhulpCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        "gft": WASTE_TYPE_GREEN,
        "papier": WASTE_TYPE_PAPER,
        "pmd+": WASTE_TYPE_PMD_GREY
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.base_url = "https://mijn.afvalhulp.nl"

    def _get_token(self, html):
        """
        Extract CSRF
        """
        meta_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
        if meta_match:
            return meta_match.group(1)

        input_match = re.search(r'name="_token"\s+value="([^"]+)"', html)
        if input_match:
            return input_match.group(1)

        return None

    def _get_ical_url(self, html):
        """
        Extract iCal URL
        """
        match = re.search(
            r"https://mijn\.afvalhulp\.nl/api/v1/ical/[a-f0-9-]{36}/calendar\.ics",
            html,
        )
        if not match:
            raise ValueError("Could not find iCal URL")
        return match.group(0)

    def _parse_ical(self, ical_text):
        """
        Parse upcoming dates from iCal
        """
        if not ical_text:
            return []

        collections = []
        event = {}
        lines = []
        for raw_line in ical_text.splitlines():
            if raw_line.startswith((" ", "\t")) and lines:
                lines[-1] += raw_line[1:]
            else:
                lines.append(raw_line)

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            field = key.split(";", 1)[0].strip().upper()
            value = value.strip()

            if field == "BEGIN" and value == "VEVENT":
                event = {}

            elif field == "SUMMARY":
                event["summary"] = value
                event["waste_type"] = self.map_waste_type(value.lower())

            elif field == "DTSTART":
                date_str = value[:8]
                if date_str.isdigit() and len(date_str) == 8:
                    event["date"] = datetime.strptime(date_str, "%Y%m%d")
                else:
                    _LOGGER.debug("Unsupported DTSTART format %s", value)

            elif field == "END" and value == "VEVENT":
                waste_type = event.get("waste_type")
                date = event.get("date")
                summary = event.get("summary", "").lower()

                if waste_type and date:
                    collection = WasteCollection.create(
                        date=date,
                        waste_type=waste_type,
                        waste_type_slug=summary,
                    )
                    if collection not in self.collections and collection not in collections:
                        collections.append(collection)
                else:
                    _LOGGER.debug("Incomplete iCal event %s", event)

                event = {}

        return collections

    def __get_data(self):
        """
        Fetch iCal data
        """
        session = requests.Session()

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": f"{self.base_url}/",
        }

        form_page = session.get(f"{self.base_url}/postcode", headers=headers, timeout=30)
        form_page.raise_for_status()

        token = self._get_token(form_page.text)
        if not token:
            raise ValueError("Could not find CSRF token")

        payload = {
            "_token": token,
            "postcode": self.postcode.replace(" ", "").upper(),
            "housenumber": str(self.street_number),
            "addition": self.suffix or "",
        }

        result = session.post(
            f"{self.base_url}/postcode",
            data=payload,
            headers=headers,
            timeout=30,
            allow_redirects=True,
        )
        result.raise_for_status()

        schedule_page = session.get(
            f"{self.base_url}/pickup-schedule",
            headers={**headers, "Referer": result.url},
            timeout=30,
        )
        schedule_page.raise_for_status()

        ical_url = self._get_ical_url(schedule_page.text)

        ical_response = session.get(
            ical_url,
            headers=headers,
            timeout=30,
        )
        ical_response.raise_for_status()

        return ical_response.text or ""

    async def update(self):
        """
        Update waste collection dates
        """
        _LOGGER.debug("Updating waste collection dates")

        try:
            collections = []

            for attempt in range(2):
                ical_text = await self.hass.async_add_executor_job(self.__get_data)
                collections = self._parse_ical(ical_text)

                if collections:
                    break

                if attempt == 0:
                    _LOGGER.warning("No waste collection dates found, retrying in 10 seconds")
                    await asyncio.sleep(10)

            self.collections.remove_all()

            for collection in collections:
                self.collections.add(collection)

            if not collections:
                _LOGGER.warning("No waste collection dates found")
                return False

            return True

        except requests.exceptions.RequestException as exc:
            _LOGGER.error("Error occurred while fetching data: %r", exc)
            return False
        except Exception as exc:
            _LOGGER.error("Unexpected error in collector: %r", exc)
            return False