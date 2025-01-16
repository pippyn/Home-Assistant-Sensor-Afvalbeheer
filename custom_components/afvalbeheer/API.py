from abc import ABC, abstractmethod
import logging
from datetime import datetime
from datetime import timedelta
import json
import requests
import re
import uuid
from rsa import pkcs1
from Crypto.PublicKey import RSA
from base64 import b64decode, b64encode

from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util
from homeassistant.components import persistent_notification

from .const import *


_LOGGER = logging.getLogger(__name__)


class WasteCollectionRepository(object):
    """
    Repository for managing waste collections.
    """

    def __init__(self):
        self.collections = []

    def __iter__(self):
        for collection in self.collections:
            yield collection

    def __len__(self):
        return len(self.collections)

    def add(self, collection):
        _LOGGER.debug(f"Adding collection: {collection}")
        self.collections.append(collection)

    def remove_all(self):
        _LOGGER.debug("Removing all collections")
        self.collections = []

    def get_sorted(self):
        _LOGGER.debug("Getting sorted collections")
        return sorted(self.collections, key=lambda x: x.date)

    def get_upcoming(self):
        _LOGGER.debug("Getting upcoming collections")
        today = datetime.now()
        return list(filter(lambda x: x.date.date() >= today.date(), self.get_sorted()))

    def get_first_upcoming(self, waste_types=None):
        _LOGGER.debug(f"Getting first upcoming collection for waste types: {waste_types}")
        upcoming = self.get_upcoming()
        first_item = upcoming[0] if upcoming else None
        return list(filter(lambda x: x.date.date() == first_item.date.date() and x.waste_type.lower() in (waste_type.lower() for waste_type in waste_types), upcoming))

    def get_upcoming_by_type(self, waste_type):
        _LOGGER.debug(f"Getting upcoming collections for waste type: {waste_type}")
        today = datetime.now()
        return list(filter(lambda x: x.date.date() >= today.date() and x.waste_type.lower() == waste_type.lower(), self.get_sorted()))

    def get_first_upcoming_by_type(self, waste_type):
        _LOGGER.debug(f"Getting first upcoming collection for waste type: {waste_type}")
        upcoming = self.get_upcoming_by_type(waste_type)
        return upcoming[0] if upcoming else None

    def get_by_date(self, date, waste_types=None):
        _LOGGER.debug(f"Getting collections by date: {date} and waste types: {waste_types}")
        if waste_types:
            return list(filter(lambda x: x.date.date() == date.date() and x.waste_type.lower() in (waste_type.lower() for waste_type in waste_types), self.get_sorted()))
        else:
            return list(filter(lambda x: x.date.date() == date.date(), self.get_sorted()))

    def get_available_waste_types(self):
        _LOGGER.debug("Getting available waste types")
        possible_waste_types = {collection.waste_type for collection in self.collections}
        return sorted(possible_waste_types, key=str.lower)
    
    def get_available_waste_type_slugs(self):
        _LOGGER.debug("Getting available waste type slugs")
        possible_waste_type_slugs = {collection.waste_type_slug for collection in self.collections}
        return sorted(possible_waste_type_slugs, key=str.lower)


class WasteCollection(object):
    """
    Represents a waste collection event.
    """

    def __init__(self):
        self.date = None
        self.waste_type = None
        self.waste_type_slug = None
        self.icon_data = None

    @classmethod
    def create(cls, date, waste_type, waste_type_slug, icon_data=None):
        collection = cls()
        collection.date = date
        collection.waste_type = waste_type
        collection.waste_type_slug = waste_type_slug
        collection.icon_data = icon_data
        return collection

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, WasteCollection):
            return (self.date == other.date and self.waste_type == other.waste_type and self.icon_data == other.icon_data)
        return NotImplemented


class WasteData(object):
    """
    Manages waste data and schedules updates.
    """

    def __init__(self, hass, waste_collector, city_name, postcode, street_name, street_number, suffix, custom_mapping, address_id, print_waste_type, print_waste_type_slugs, update_interval, customer_id):
        self.hass = hass
        self.waste_collector = waste_collector
        self.city_name = city_name
        self.postcode = postcode
        self.street_name = street_name
        self.street_number = street_number
        self.suffix = suffix
        self.address_id = address_id
        self.print_waste_type = print_waste_type
        self.print_waste_type_slugs = print_waste_type_slugs
        self.collector = None
        self.update_interval = update_interval
        self.customer_id = customer_id
        self.custom_mapping = custom_mapping
        self.__select_collector()

    def __select_collector(self):
        _LOGGER.debug(f"Selecting collector for waste_collector: {self.waste_collector}")
        common_args = [self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix, self.custom_mapping]

        collector_mapping = {
            **{key: (XimmioCollector, common_args + [self.address_id, self.customer_id]) for key in XIMMIO_COLLECTOR_IDS.keys()},
            "mijnafvalwijzer": (AfvalwijzerCollector, common_args),
            "afvalstoffendienstkalender": (AfvalwijzerCollector, common_args),
            "afvalalert": (AfvalAlertCollector, common_args),
            "deafvalapp": (DeAfvalAppCollector, common_args),
            "circulus": (CirculusCollector, common_args),
            "limburg.net": (LimburgNetCollector, common_args + [self.street_name, self.city_name]),
            "montferland": (MontferlandNetCollector, common_args),
            "omrin": (OmrinCollector, common_args),
            "recycleapp": (RecycleApp, common_args + [self.street_name]),
            "rd4": (RD4Collector, common_args),
            "cleanprofs": (CleanprofsCollector, common_args),
            "rova": (ROVACollector, common_args),
            "drimmelen": (StraatbeeldCollector, common_args),
            **{key: (BurgerportaalCollector, common_args) for key in BURGERPORTAAL_COLLECTOR_IDS.keys()},
            **{key: (OpzetCollector, common_args) for key in OPZET_COLLECTOR_URLS.keys()},
        }

        collector_class, args = collector_mapping.get(self.waste_collector, (None, None))

        if collector_class:
            self.collector = collector_class(*args)
        else:
            persistent_notification.create(
                self.hass,
                f'Waste collector "{self.waste_collector}" not found!',
                f'Afvalwijzer {self.waste_collector}',
                f'{NOTIFICATION_ID}_collectornotfound_{self.waste_collector}'
            )

    async def schedule_update(self, interval):
        _LOGGER.debug(f"Scheduling update with interval: {interval}")
        nxt = dt_util.utcnow() + interval
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)

    async def async_update(self, *_):
        _LOGGER.debug("Performing async update")
        await self.collector.update()
        if self.update_interval is not None and self.update_interval != 0:
            await self.schedule_update(timedelta(hours=self.update_interval))
        else:
            await self.schedule_update(SCHEDULE_UPDATE_INTERVAL)
        if self.print_waste_type:
            persistent_notification.create(
                self.hass,
                f'Available waste types: {", ".join(self.collector.collections.get_available_waste_types())}',
                f'Afvalwijzer {self.waste_collector}',
                f'{NOTIFICATION_ID}_availablewastetypes_{self.waste_collector}')
            self.print_waste_type = False
        if self.print_waste_type_slugs:
            persistent_notification.create(
                self.hass,
                f'Waste type slugs used by API: {", ".join(self.collector.collections.get_available_waste_type_slugs())}',
                f'Afvalwijzer {self.waste_collector}',
                f'{NOTIFICATION_ID}_availablewastetypeslugs_{self.waste_collector}')
            self.print_waste_type = False

    @property
    def collections(self):
        return self.collector.collections


class WasteCollector(ABC):
    """
    Abstract base class for waste collectors.
    """

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        self.hass = hass
        self.waste_collector = waste_collector
        self.postcode = postcode
        self.street_number = street_number
        self.suffix = suffix
        self.custom_mapping = custom_mapping
        self.collections = WasteCollectionRepository()

    @abstractmethod
    async def update(self):
        pass

    def map_waste_type(self, name):
        _LOGGER.debug(f"Mapping waste type for name: {name}")
        if self.custom_mapping:
            for from_type, to_type in self.custom_mapping.items():
                if from_type.lower() in name.lower():
                    return to_type
        for from_type, to_type in self.WASTE_TYPE_MAPPING.items():
            if from_type.lower() in name.lower():
                return to_type
        return name


class AfvalAlertCollector(WasteCollector):
    """
    Collector for AfvalAlert waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'tak-snoeiafval': WASTE_TYPE_BRANCHES,
        # 'gemengde plastics': WASTE_TYPE_PLASTIC,
        # 'grof huisvuil': WASTE_TYPE_BULKLITTER,
        # 'grof huisvuil afroep': WASTE_TYPE_BULKLITTER,
        # 'tak-snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        # 'fles-groen-glas': WASTE_TYPE_GLASS,
        'gft': WASTE_TYPE_GREEN,
        # 'batterij': WASTE_TYPE_KCA,
        'rest': WASTE_TYPE_GREY,
        'milb': WASTE_TYPE_MILIEUB,
        # 'p-k': WASTE_TYPE_PAPER,
        # 'shirt-textiel': WASTE_TYPE_TEXTILE,
        'kerst': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://www.afvalalert.nl/kalender"

    def __get_data(self):
        _LOGGER.debug("Fetching data from AfvalAlert")
        get_url = '{}/{}/{}{}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using AfvalAlert API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response['items']:
                if not item['date']:
                    continue

                waste_type = self.map_waste_type(item['type'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['date'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class AfvalwijzerCollector(WasteCollector):
    """
    Collector for Afvalwijzer waste data.
    """
    WASTE_TYPE_MAPPING = {
        'dhm': WASTE_TYPE_PAPER_PMD,
        'restgft': WASTE_TYPE_GREENGREY,
        'takken': WASTE_TYPE_BRANCHES,
        'grofvuil': WASTE_TYPE_BULKLITTER,
        'tuinafval': WASTE_TYPE_BULKYGARDENWASTE,
        'glas': WASTE_TYPE_GLASS,
        'gft': WASTE_TYPE_GREEN,
        'keukenafval': WASTE_TYPE_GREEN,
        'kcalocatie': WASTE_TYPE_KCA_LOCATION,
        'kca': WASTE_TYPE_KCA,
        'restafval': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'gkbp': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstbomen': WASTE_TYPE_TREE,
        'pd': WASTE_TYPE_PACKAGES,
        'md': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.apikey = '5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca'
        self.waste_collector_url = self.waste_collector

    def __get_data(self):
        _LOGGER.debug("Fetching data from Afvalwijzer")
        get_url = 'https://api.{}.nl/webservices/appsinput/?apikey={}&method=postcodecheck&postcode={}&street=&huisnummer={}&toevoeging={}&app_name=afvalwijzer&platform=web&afvaldata={}&langs=nl'.format(
                self.waste_collector_url, self.apikey, self.postcode, self.street_number, self.suffix, datetime.today().strftime('%Y-%m-%d'))
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Afvalwijzer API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            data = []

            if 'ophaaldagen' in response:
                data = data + response['ophaaldagen']['data']

            if 'ophaaldagenNext' in response:
                data = data + response['ophaaldagenNext']['data']

            if not data:
                _LOGGER.error('No Waste data found!')
                return

            for item in data:
                if not item['date']:
                    continue

                waste_type = self.map_waste_type(item['type'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['date'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class BurgerportaalCollector(WasteCollector):
    """
    Collector for Burgerportaal waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'opk': WASTE_TYPE_PAPER,
        'pmdrest': WASTE_TYPE_PMD_GREY,
        'rest': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.company_code = BURGERPORTAAL_COLLECTOR_IDS[self.waste_collector]
        self.apikey = 'AIzaSyA6NkRqJypTfP-cjWzrZNFJzPUbBaGjOdk'
        self.refresh_token = ''
        self.id_token = ''
        self.address_id = ''

    def __fetch_refresh_token(self):
        _LOGGER.debug("Fetching refresh token from Burgerportaal")
        response = requests.post("https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={}".format(self.apikey)).json()
        if not response:
            _LOGGER.error('Unable to fetch refresh token!')
            return
        self.refresh_token = response['refreshToken']
        self.id_token = response['idToken']

    def __fetch_id_token(self):
        _LOGGER.debug("Fetching ID token from Burgerportaal")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type' : 'refresh_token',
            'refresh_token' : self.refresh_token
        }

        response = requests.post("https://securetoken.googleapis.com/v1/token?key={}".format(self.apikey), headers=headers, data=data).json()
        if not response:
            _LOGGER.error('Unable to fetch refresh token!')
            return
        self.id_token = response['id_token']

    def __fetch_address_id(self):
        _LOGGER.debug("Fetching address ID from Burgerportaal")
        headers = {
            'authorization': self.id_token
        }

        response = requests.get("https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{}/address?zipcode={}&housenumber={}".format(
            self.company_code, self.postcode, self.street_number), headers=headers).json()
        if not response:
            _LOGGER.error('Unable to fetch refresh token!')
            return

        if self.suffix:
            for address in response:
                if 'addition' in address and address['addition'] == self.suffix.upper():
                    self.address_id = address['addressId']

        if not self.address_id:
            self.address_id = response[-1]['addressId']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Burgerportaal")
        headers = {
            'authorization': self.id_token
        }

        response = requests.get("https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{}/address/{}/calendar".format(
            self.company_code, self.address_id), headers=headers).json()
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Burgerportaal API")

        self.collections.remove_all()

        try:
            if not self.refresh_token:
                await self.hass.async_add_executor_job(self.__fetch_refresh_token)
            else:
                await self.hass.async_add_executor_job(self.__fetch_id_token)

            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address_id)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['collectionDate']:
                    continue

                waste_type = self.map_waste_type(item['fraction'].lower())
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['collectionDate'].split("T")[0], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['fraction'].lower()
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


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

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response or 'customData' not in response or not response['customData']['response']['garbage']:
                _LOGGER.error('No Waste data found!')
                return

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


class CleanprofsCollector(WasteCollector):
    """
    Collector for Cleanprofs waste data.
    """
    WASTE_TYPE_MAPPING = {
        'GFT': WASTE_TYPE_GREEN,
        'RST': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://cleanprofs.jmsdev.nl/"

    def __get_data(self):
        _LOGGER.debug("Fetching data from Cleanprofs")
        get_url = '{}api/get-plannings-address?zipcode={}&house_number={}'.format(
                self.main_url, self.postcode, self.street_number)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Cleanprofs API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['full_date']:
                    continue

                waste_type = self.map_waste_type(item['product_name'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['full_date'], '%Y-%m-%d').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['product_name']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class DeAfvalAppCollector(WasteCollector):
    """
    Collector for DeAfvalApp waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gemengde plastics': WASTE_TYPE_PLASTIC,
        'zak_blauw': WASTE_TYPE_GREY,
        'pbp': WASTE_TYPE_PACKAGES,
        'rest': WASTE_TYPE_GREY,
        'kerstboom': WASTE_TYPE_TREE
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "http://dataservice.deafvalapp.nl"

    def __get_data(self):
        _LOGGER.debug("Fetching data from DeAfvalApp")
        get_url = '{}/dataservice/DataServiceServlet?service=OPHAALSCHEMA&land=NL&postcode={}&straatId=0&huisnr={}&huisnrtoev={}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using DeAfvalApp API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.text

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for rows in response.strip().split('\n'):
                waste_type = self.map_waste_type(rows.split(';')[0])
                if not waste_type:
                    continue

                for ophaaldatum in rows.split(';')[1:-1]:
                    if not ophaaldatum:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(ophaaldatum, '%d-%m-%Y'),
                        waste_type=waste_type,
                        waste_type_slug=rows.split(';')[0]
                    )
                    if collection not in self.collections:
                        self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class LimburgNetCollector(WasteCollector):
    """
    Collector for Limburg.net waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'tak-snoeiafval': WASTE_TYPE_BRANCHES,
        # 'gemengde plastics': WASTE_TYPE_PLASTIC,
        'Grofvuil': WASTE_TYPE_BULKLITTER,
        'Groenafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Tuin- En Snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Tuinafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Keukenafval': WASTE_TYPE_GREEN,
        # 'grof huisvuil afroep': WASTE_TYPE_BULKLITTER,
        # 'tak-snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Glas': WASTE_TYPE_GLASS,
        'GFT': WASTE_TYPE_GREEN,
        # 'batterij': WASTE_TYPE_KCA,
        'Huisvuil': WASTE_TYPE_GREY,
        'PMD': WASTE_TYPE_PACKAGES,
        'Papier': WASTE_TYPE_PAPER,
        'Textiel': WASTE_TYPE_TEXTILE,
        # 'kerstboom': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, street_name, city_name):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.city_name = city_name
        self.street_name = street_name.replace(" ", "+")
        self.main_url = "https://limburg.net/api-proxy/public"
        self.city_id = None
        self.street_id = None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Limburg.net")
        response = requests.get('{}/afval-kalender/gemeenten/search?query={}'.format(
            self.main_url, self.city_name)).json()

        if not response[0]['nisCode']:
            _LOGGER.error('City not found!')
            return

        self.city_id = response[0]["nisCode"]

        response = requests.get('{}/afval-kalender/gemeente/{}/straten/search?query={}'.format(
            self.main_url, self.city_id, self.street_name)).json()

        if not response[0]['nummer']:
            _LOGGER.error('Street not found!')
            return

        self.street_id = response[0]['nummer']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Limburg.net")
        data = []

        for x in range(0, 3):
            if x == 0:
                today = datetime.today()
            else:
                today = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            year = today.year
            month = today.month
            get_url = '{}/kalender/{}/{}-{}?straatNummer={}&huisNummer={}&toevoeging={}'.format(
                    self.main_url, self.city_id, year, month, self.street_id, self.street_number, self.suffix)
            month_json = requests.get(get_url).json()
            data = data + month_json['events']

        return data

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Limburg.net API")

        self.collections.remove_all()

        try:
            if not self.city_id or not self.street_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['date']:
                    continue

                waste_type = self.map_waste_type(item['title'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['title']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class MontferlandNetCollector(WasteCollector):
    """
    Collector for Montferland waste data.
    """
    WASTE_TYPE_MAPPING = {
        'Glas': WASTE_TYPE_GLASS,
        'GFT': WASTE_TYPE_GREEN,
        'Rest afval': WASTE_TYPE_GREY,
        'PMD': WASTE_TYPE_PACKAGES,
        'Papier': WASTE_TYPE_PAPER,
        'Textiel': WASTE_TYPE_TEXTILE,
        # 'kerstboom': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "http://afvalwijzer.afvaloverzicht.nl/"
        self.query_start = "?Username=GSD&Password=gsd$2014"
        self.administratie_id = None
        self.adres_id = None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Montferland")
        response = requests.get('{}Login.ashx{}&Postcode={}&Huisnummer={}&Toevoeging='.format(
            self.main_url, self.query_start, self.postcode, self.street_number, self.suffix)).json()

        if not response[0]['AdresID']:
            _LOGGER.error('AdresID not found!')
            return

        if not response[0]['AdministratieID']:
            _LOGGER.error('AdministratieID not found!')
            return

        self.adres_id = response[0]["AdresID"]
        self.administratie_id = response[0]["AdministratieID"]

    def __get_data(self):
        _LOGGER.debug("Fetching data from Montferland")
        data = []

        today = datetime.today()
        year = today.year

        get_url = '{}/OphaalDatums.ashx/{}&ADM_ID={}&ADR_ID={}&Jaar={}'.format(
                self.main_url, self.query_start, self.administratie_id, self.adres_id, year)
        data = requests.get(get_url).json()

        return data

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Montferland API")

        self.collections.remove_all()

        try:
            if not self.administratie_id or not self.adres_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            response = await self.hass.async_add_executor_job(self.__get_data)

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['Datum']:
                    continue

                waste_type = self.map_waste_type(item['Soort'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['Datum'], '%Y-%m-%dT%H:%M:%S'),
                    waste_type=waste_type,
                    waste_type_slug=item['Soort']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class OmrinCollector(WasteCollector):
    """
    Collector for Omrin waste data.
    """
    WASTE_TYPE_MAPPING = {
        # 'BRANCHES': WASTE_TYPE_BRANCHES,
        'Grofvuil': WASTE_TYPE_BULKLITTER,
        'Grofvuil en elektrische apparaten': WASTE_TYPE_BULKLITTER,
        # 'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        # 'GLASS': WASTE_TYPE_GLASS,
        'Biobak op afroep': WASTE_TYPE_GREEN,
        'Biobak': WASTE_TYPE_GREEN,
        'GFT': WASTE_TYPE_GREEN,
        # 'GREY': WASTE_TYPE_GREY,
        'KCA': WASTE_TYPE_KCA,
        'Chemisch afval': WASTE_TYPE_KCA,
        'Sortibak': WASTE_TYPE_SORTI,
        'Papier': WASTE_TYPE_PAPER,
        # 'REMAINDER': WASTE_TYPE_REMAINDER,
        # 'TEXTILE': WASTE_TYPE_TEXTILE,
        # 'TREE': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://api-omrin.freed.nl/Account"
        self.appId = uuid.uuid1().__str__()
        self.publicKey = None

    def __fetch_publickey(self):
        _LOGGER.debug("Fetching public key from Omrin")
        response = requests.post("{}/GetToken/".format(self.main_url), json={'AppId': self.appId, 'AppVersion': '', 'OsVersion': '', 'Platform': 'HomeAssistant'}).json()
        self.publicKey = b64decode(response['PublicKey'])

    def __get_data(self):
        _LOGGER.debug("Fetching data from Omrin")
        rsaPublicKey = RSA.importKey(self.publicKey)
        requestBody = {'a': False, 'Email': None, 'Password': None, 'PostalCode': self.postcode, 'HouseNumber': self.street_number}

        encryptedRequest = pkcs1.encrypt(json.dumps(requestBody).encode(), rsaPublicKey)
        base64EncodedRequest = b64encode(encryptedRequest).decode("utf-8")

        response = requests.post("{}/FetchAccount/".format(self.main_url) + self.appId, '"' + base64EncodedRequest + '"', timeout=60).json()
        return response['CalendarV2']

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Omrin API")

        try:
            if not self.publicKey:
                await self.hass.async_add_executor_job(self.__fetch_publickey)

            response = await self.hass.async_add_executor_job(self.__get_data)
            self.collections.remove_all()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['Datum']:
                    continue

                if item['Datum'] == '0001-01-01T00:00:00':
                    continue

                waste_type = self.map_waste_type(item['Omschrijving'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['Datum'], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item['Omschrijving']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class OpzetCollector(WasteCollector):
    """
    Collector for Opzet waste data.
    """
    WASTE_TYPE_MAPPING = {
        'pbd/papier': WASTE_TYPE_PAPER_PMD,
        'snoeiafval': WASTE_TYPE_BRANCHES,
        'sloop': WASTE_TYPE_BULKLITTER,
        'glas': WASTE_TYPE_GLASS,
        'duobak': WASTE_TYPE_GREENGREY,
        'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        'groene container': WASTE_TYPE_GREEN,
        'chemisch': WASTE_TYPE_KCA,
        'kca': WASTE_TYPE_KCA,
        'tariefzak restafval': WASTE_TYPE_GREY_BAGS,
        'restafvalzakken': WASTE_TYPE_GREY_BAGS,
        'rest': WASTE_TYPE_GREY,
        'grijze container': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstb': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
        'pbd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = OPZET_COLLECTOR_URLS[self.waste_collector]
        self.bag_id = None
        if waste_collector == "suez":
            self._verify = False
        else:
            self._verify = True

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Opzet")
        response = requests.get(
            "{}/rest/adressen/{}-{}".format(self.main_url, self.postcode, self.street_number), verify=self._verify).json()

        if not response:
            _LOGGER.error('Address not found!')
            return

        if len(response) > 1 and self.suffix:
            for item in response:
                if item['huisletter'] == self.suffix or item['huisnummerToevoeging'] == self.suffix:
                    self.bag_id = item['bagId']
                    break
        else:
            self.bag_id = response[0]['bagId']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Opzet")
        get_url = "{}/rest/adressen/{}/afvalstromen".format(
                self.main_url,
                self.bag_id)
        return requests.get(get_url, verify=self._verify)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Opzet API")

        self.collections.remove_all()

        try:
            if not self.bag_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['ophaaldatum']:
                    continue

                waste_type = self.map_waste_type(item['menu_title'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['ophaaldatum'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    waste_type_slug=item['menu_title'],
                    icon_data=item['icon_data']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class RD4Collector(WasteCollector):
    """
    Collector for RD4 waste data.
    """
    WASTE_TYPE_MAPPING = {
        'pruning': WASTE_TYPE_BRANCHES,
        # 'sloop': WASTE_TYPE_BULKLITTER,
        # 'glas': WASTE_TYPE_GLASS,
        # 'duobak': WASTE_TYPE_GREENGREY,
        # 'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        # 'chemisch': WASTE_TYPE_KCA,
        # 'kca': WASTE_TYPE_KCA,
        'residual': WASTE_TYPE_GREY,
        # 'plastic': WASTE_TYPE_PACKAGES,
        'paper': WASTE_TYPE_PAPER,
        'best_bag': "best-tas",
        'christmas_trees': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = 'https://data.rd4.nl/api/v1/waste-calendar'
        self.postcode_split = re.search(r"(\d\d\d\d) ?([A-z][A-z])", self.postcode)
        self.postcode = self.postcode_split.group(1) + '+' + self.postcode_split.group(2).upper()

    def __get_data(self):
        _LOGGER.debug("Fetching data from RD4")
        self.today = datetime.today()
        self.year = self.today.year
        response = requests.get(
            '{}?postal_code={}&house_number={}&house_number_extension={}&year={}'.format(self.main_url, self.postcode, self.street_number, self.suffix, self.year)
        )
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using RD4 API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            if not response["success"]:
                _LOGGER.error('Address not found!')
                return

            for item in response["data"]["items"][0]:

                waste_type = self.map_waste_type(item["type"])
                date = item["date"]

                if not waste_type or not date:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(date, "%Y-%m-%d"),
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class ROVACollector(WasteCollector):
    """
    Collector for ROVA waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'papier': WASTE_TYPE_PAPER,
        'pmd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = 'https://www.rova.nl'

    def __get_data(self):
        _LOGGER.debug("Fetching data from ROVA")
        self.today = datetime.today()
        self.year = self.today.year
        response = requests.get(
            '{}/api/waste-calendar/upcoming?houseNumber={}&addition={}&postalcode={}&take=10'.format(self.main_url, self.street_number, self.suffix, self.postcode)
        )
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using ROVA API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                waste_type = self.map_waste_type(item["wasteType"]["title"])
                date = item["date"]

                if not waste_type or not date:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(date, '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type,
                    waste_type_slug=item["wasteType"]["title"]
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class RecycleApp(WasteCollector):
    """
    Collector for RecycleApp waste data.
    """
    WASTE_TYPE_MAPPING = {
        'grof': WASTE_TYPE_BULKLITTER,
        # 'glas': WASTE_TYPE_GLASS,
        'glas': WASTE_TYPE_GLASS,
        # 'duobak': WASTE_TYPE_GREENGREY,
        'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        # 'chemisch': WASTE_TYPE_KCA,
        # 'kca': WASTE_TYPE_KCA,
        'huisvuil': WASTE_TYPE_GREY,
        'rest': WASTE_TYPE_GREY,
        'ordures ménagères': WASTE_TYPE_GREY,
        # 'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        # 'kerstb': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
        'gemengde': WASTE_TYPE_PLASTIC,
        'snoeihout': WASTE_TYPE_BRANCHES,
        'zachte plastics': WASTE_TYPE_SOFT_PLASTIC,
        'roze zak': WASTE_TYPE_SOFT_PLASTIC,
        'déchets résiduels': WASTE_TYPE_GREY,
        'déchets organiques': WASTE_TYPE_GREEN,
        'omb': WASTE_TYPE_GREY,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, street_name):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.street_name = street_name
        self.main_url = 'https://www.recycleapp.be/api/app/v1/'
        self.xsecret = 'Op2tDi2pBmh1wzeC5TaN2U3knZan7ATcfOQgxh4vqC0mDKmnPP2qzoQusmInpglfIkxx8SZrasBqi5zgMSvyHggK9j6xCQNQ8xwPFY2o03GCcQfcXVOyKsvGWLze7iwcfcgk2Ujpl0dmrt3hSJMCDqzAlvTrsvAEiaSzC9hKRwhijQAFHuFIhJssnHtDSB76vnFQeTCCvwVB27DjSVpDmq8fWQKEmjEncdLqIsRnfxLcOjGIVwX5V0LBntVbeiBvcjyKF2nQ08rIxqHHGXNJ6SbnAmTgsPTg7k6Ejqa7dVfTmGtEPdftezDbuEc8DdK66KDecqnxwOOPSJIN0zaJ6k2Ye2tgMSxxf16gxAmaOUqHS0i7dtG5PgPSINti3qlDdw6DTKEPni7X0rxM'
        self.xconsumer = 'recycleapp.be'
        self.accessToken = ''
        self.postcode_id = ''
        self.street_id = ''

    def __get_headers(self):
        _LOGGER.debug("Getting headers for RecycleApp")
        headers = {
            'x-secret': self.xsecret,
            'x-consumer': self.xconsumer,
            'User-Agent': '',
            'Authorization': self.accessToken,
        }
        return headers

    def __get_access_token(self):
        _LOGGER.debug("Fetching access token from RecycleApp")
        response = requests.get("{}access-token".format(self.main_url), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for accessToken')
            return
        self.accessToken = response.json()['accessToken']

    def __get_location_ids(self):
        _LOGGER.debug("Fetching location IDs from RecycleApp")
        response = requests.get("{}zipcodes?q={}".format(self.main_url, self.postcode), headers=self.__get_headers())
        if response.status_code == 401:
            self.__get_access_token()
            response = requests.get("{}zipcodes?q={}".format(self.main_url, self.postcode), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for postcode_id')
            return
        self.postcode_id = response.json()['items'][0]['id']
        response = requests.get("{}streets?q={}&zipcodes={}".format(self.main_url, self.street_name, self.postcode_id), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for street_id')
            return
        for item in response.json()['items']:
            if item['name'] == self.street_name:
                self.street_id = item['id']
        if not self.street_id:
            self.street_id = response.json()['items'][0]['id']

    def __get_data(self):
        _LOGGER.debug("Fetching data from RecycleApp")
        startdate = datetime.now().strftime("%Y-%m-%d")
        enddate = (datetime.now() + timedelta(days=+60)).strftime("%Y-%m-%d")
        response = requests.get("{}collections?zipcodeId={}&streetId={}&houseNumber={}&fromDate={}&untilDate={}&size=100".format(
            self.main_url,
            self.postcode_id,
            self.street_id,
            self.street_number,
            startdate,
            enddate),
            headers=self.__get_headers())
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using RecycleApp API")

        try:
            await self.hass.async_add_executor_job(self.__get_access_token)

            if (not self.postcode_id or not self.street_id) and self.accessToken:
                await self.hass.async_add_executor_job(self.__get_location_ids)

            if not self.postcode_id or not self.street_id or not self.accessToken:
                return

            r = await self.hass.async_add_executor_job(self.__get_data)
            if r.status_code != 200:
                _LOGGER.error('Invalid response from server for collection data')
                return
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            for item in response['items']:
                if not item['timestamp']:
                    continue
                if not item['fraction'] or not 'name' in item['fraction'] or not 'nl' in item['fraction']['name']:
                    continue
                if 'exception' in item and 'replacedBy' in item['exception']:
                    continue

                waste_type = self.map_waste_type(item['fraction']['name']['nl'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['timestamp'], '%Y-%m-%dT%H:%M:%S.000Z'),
                    waste_type=waste_type,
                    waste_type_slug=item['fraction']['name']['nl']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class StraatbeeldCollector(WasteCollector):
    """
    Collector for Straatbeeld waste data.
    """
    WASTE_TYPE_MAPPING = {
        'gft': WASTE_TYPE_GREEN,
        'rest': WASTE_TYPE_GREY,
        'pmd': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'kerstboom': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.main_url = "https://drimmelen-afvalkalender-api.straatbeeld.online"

    def __get_data(self):
        _LOGGER.debug("Fetching data from Straatbeeld")
        data = {
            "postal_code": self.postcode,
            "house_number": self.street_number,
            "house_letter": self.suffix,
        }

        return requests.post(f"{self.main_url}/find-address", data=data)

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Straatbeeld API")

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            if r.status_code != 200:
                _LOGGER.error('Invalid response from server for collection data')
                return
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            self.collections.remove_all()

            for _, months in response['collections'].items():
                for _, days in months.items():
                    for day in days:

                        date = datetime.strptime(day['date']['formatted'], '%Y-%m-%d')

                        for item in day['data']:

                            waste_type = self.map_waste_type(item['id'])
                            if not waste_type:
                                continue

                            collection = WasteCollection.create(
                                date=date,
                                waste_type=waste_type,
                                waste_type_slug=item['id']
                            )
                            if collection not in self.collections:
                                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False

class XimmioCollector(WasteCollector):
    """
    Collector for Ximmio waste data.
    """
    WASTE_TYPE_MAPPING = {
        'BRANCHES': WASTE_TYPE_BRANCHES,
        'BULKLITTER': WASTE_TYPE_BULKLITTER,
        'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        'BULKYRESTWASTE': WASTE_TYPE_PMD_GREY,
        'GLASS': WASTE_TYPE_GLASS,
        'GREENGREY': WASTE_TYPE_GREENGREY,
        'GREEN': WASTE_TYPE_GREEN,
        'GREY': WASTE_TYPE_GREY,
        'KCA': WASTE_TYPE_KCA,
        'PLASTIC': WASTE_TYPE_PACKAGES,
        'PACKAGES': WASTE_TYPE_PACKAGES,
        'PAPER': WASTE_TYPE_PAPER,
        'REMAINDER': WASTE_TYPE_REMAINDER,
        'TEXTILE': WASTE_TYPE_TEXTILE,
        'TREE': WASTE_TYPE_TREE,
    }

    XIMMIO_URLS = {
        'avalex': "https://wasteprod2api.ximmio.com",
        'meerlanden': "https://wasteprod2api.ximmio.com",
        'rad': "https://wasteprod2api.ximmio.com",
        'westland': "https://wasteprod2api.ximmio.com",
        'woerden': "https://wasteprod2api.ximmio.com",
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, address_id, customer_id):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        if self.waste_collector in self.XIMMIO_URLS.keys():
            self.main_url = self.XIMMIO_URLS[self.waste_collector]
        else:
            self.main_url = "https://wasteapi.ximmio.com"
        self.company_code = XIMMIO_COLLECTOR_IDS[self.waste_collector]
        self.community = ""
        self.customer_id = customer_id
        self.address_id = address_id if address_id else None

    def __fetch_address(self):
        _LOGGER.debug("Fetching address from Ximmio")
        data = {
            "postCode": self.postcode,
            "houseNumber": self.street_number,
            "companyCode": self.company_code
        }

        if self.customer_id:
            data["commercialNumber"] = self.customer_id

        response = requests.post(
            "{}/api/FetchAdress".format(self.main_url),
            data=data).json()

        if not response['dataList']:
            _LOGGER.error('Address not found!')
            return

        if response['dataList'][0]['Community']:
            self.community = response['dataList'][0]['Community']

        self.address_id = response['dataList'][0]['UniqueId']

    def __get_data(self):
        _LOGGER.debug("Fetching data from Ximmio")
        data = {
            "uniqueAddressID": self.address_id,
            "startDate": datetime.now().strftime('%Y-%m-%d'),
            "endDate": (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
            "companyCode": self.company_code,
            "community": self.community
        }

        if self.customer_id:
            data["isCommercial"] = True

        response = requests.post(
            "{}/api/GetCalendar".format(self.main_url),
            data=data)
        return response

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Ximmio API")

        self.collections.remove_all()

        try:
            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response or not response['dataList']:
                _LOGGER.error('No Waste data found!')
                return

            for item in response['dataList']:
                for date in item['pickupDates']:
                    waste_type = self.map_waste_type(item['_pickupTypeText'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(date, '%Y-%m-%dT%H:%M:%S'),
                        waste_type=waste_type,
                        waste_type_slug=item['_pickupTypeText']
                    )
                    if collection not in self.collections:
                        self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


def get_wastedata_from_config(hass, config):
    _LOGGER.debug("Getting WasteData from config")
    _LOGGER.debug("Get Rest API retriever")
    city_name = config.get(CONF_CITY_NAME)
    postcode = config.get(CONF_POSTCODE)
    street_name = config.get(CONF_STREET_NAME)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX)
    address_id = config.get(CONF_ADDRESS_ID)
    waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
    print_waste_type = config.get(CONF_PRINT_AVAILABLE_WASTE_TYPES)
    print_waste_type_slugs = config.get(CONF_PRINT_AVAILABLE_WASTE_TYPE_SLUGS)
    update_interval = config.get(CONF_UPDATE_INTERVAL)
    customer_id = config.get(CONF_CUSTOMER_ID)
    custom_mapping = config.get(CONF_CUSTOM_MAPPING)
    config["id"] = _format_id(waste_collector, postcode, street_number)

    if waste_collector in DEPRECATED_AND_NEW_WASTECOLLECTORS:
        persistent_notification.create(
            hass,
            f"Update your config to use {DEPRECATED_AND_NEW_WASTECOLLECTORS[waste_collector]}! You are still using {waste_collector} as a waste collector, which is deprecated. Check your automations and lovelace config, as the sensor names may also be changed!",
            f"Afvalbeheer {waste_collector}",
            f"{NOTIFICATION_ID}_update_config_{waste_collector}",
        )
        waste_collector = DEPRECATED_AND_NEW_WASTECOLLECTORS[waste_collector]

    if waste_collector in ["limburg.net"] and not city_name:
        persistent_notification.create(
            hass,
            f"Config invalid! Cityname is required for {waste_collector}",
            f"Afvalbeheer {waste_collector}",
            f"{NOTIFICATION_ID}_invalid_config_{waste_collector}",
        )
        return

    if waste_collector in ["limburg.net", "recycleapp"] and not street_name:
        persistent_notification.create(
            hass,
            f"Config invalid! Streetname is required for {waste_collector}",
            f"Afvalbeheer {waste_collector}",
            f"{NOTIFICATION_ID}_invalid_config_{waste_collector}",
        )
        return

    return WasteData(
        hass,
        waste_collector,
        city_name,
        postcode,
        street_name,
        street_number,
        suffix,
        custom_mapping,
        address_id,
        print_waste_type,
        print_waste_type_slugs,
        update_interval,
        customer_id,
    )


def _format_id(waste_collector, postcode, house_number):
    _LOGGER.debug(f"Formatting ID for waste_collector: {waste_collector}, postcode: {postcode}, house_number: {house_number}")
    return waste_collector + "-" + postcode + "-" + str(house_number)
