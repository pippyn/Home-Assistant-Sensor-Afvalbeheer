"""
Circulus collector for waste data from Circulus API.
"""
import logging
import re
from datetime import datetime, timedelta
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import WASTE_TYPE_PAPER, WASTE_TYPE_GREEN, WASTE_TYPE_GREY, WASTE_TYPE_PACKAGES

_LOGGER = logging.getLogger(__name__)


class CirculusCollector(WasteCollector):
    """
    Collector for Circulus waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'BRANCHES': WASTE_TYPE_BRANCHES,
        # 'BULKLITTER': WASTE_TYPE_BULKLITTER,
        # 'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        'DROCO': WASTE_TYPE_PAPER,
        # 'GLASS': WASTE_TYPE_GLASS,
        'GFT': WASTE_TYPE_GREEN,
        'REST': WASTE_TYPE_GREY,
        # 'KCA': WASTE_TYPE_KCA,
        'ZWAKRA': WASTE_TYPE_PACKAGES,
        'PMD': WASTE_TYPE_PACKAGES,
        'PAP': WASTE_TYPE_PAPER,
        # 'TEXTILE': WASTE_TYPE_TEXTILE,
        # 'TREE': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://mijn.circulus.nl"

    def __get_data(self):
        _LOGGER.debug("Fetching data from Circulus")
        r = requests.get(self.main_url)
        cookies = r.cookies
        session_cookie = ""
        logged_in_cookies = ""

        for item in cookies.items():
            if item[0] == "CB_SESSION":
                session_cookie = item[1]

        if session_cookie:
            authenticityToken = re.search('__AT=(.*)&___TS=', session_cookie).group(1)
            data = {
                'authenticityToken': authenticityToken,
                'zipCode': self.postcode,
                'number': self.street_number,
                }

            r = requests.post(
                '{}/register/zipcode.json'.format(self.main_url), data=data, cookies=cookies
            )

            json_response_data = r.json()
            if json_response_data["flashMessage"]:
                addresses = json_response_data["customData"]["addresses"]
                authenticationUrl = ""
                if self.suffix:
                    search_pattern = f' {self.street_number} {self.suffix.lower()}'
                    for address in addresses:
                        if re.search(search_pattern, address["address"]):
                            authenticationUrl = address["authenticationUrl"]
                            break
                else:
                    authenticationUrl = addresses[0]["authenticationUrl"]
                if authenticationUrl:
                    r = requests.get(self.main_url + authenticationUrl, cookies=cookies)

            logged_in_cookies = r.cookies
        else:
            _LOGGER.error("Unable to get Session Cookie")

        if logged_in_cookies:
            startDate = (datetime.today() - timedelta(days=14)).strftime("%Y-%m-%d")
            endDate =  (datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d")

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.get('{}/afvalkalender.json?from={}&till={}'.format(
                self.main_url,
                startDate,
                endDate
                ), headers=headers, cookies=logged_in_cookies)
            return response
        else:
            _LOGGER.error("Unable to get Logged-in Cookie")

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Circulus API")

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response or 'customData' not in response or not response['customData']['response']['garbage']:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response['customData']['response']['garbage']:
                for date in item['dates']:
                    waste_type = self.map_waste_type(item['code'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(date, '%Y-%m-%d'),
                        waste_type=waste_type,
                        waste_type_slug=item['code']
                    )
                    if collection not in self.collections:
                        self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False