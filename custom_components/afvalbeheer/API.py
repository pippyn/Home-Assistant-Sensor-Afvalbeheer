import abc
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

    def __init__(self):
        self.collections = []

    def __iter__(self):
        for collection in self.collections:
            yield collection

    def __len__(self):
        return len(self.collections)

    def add(self, collection):
        self.collections.append(collection)

    def remove_all(self):
        self.collections = []

    def get_sorted(self):
        return sorted(self.collections, key=lambda x: x.date)

    def get_upcoming_by_type(self, waste_type):
        today = datetime.now()
        return list(filter(lambda x: x.date.date() >= today.date() and x.waste_type == waste_type, self.get_sorted()))

    def get_first_upcoming_by_type(self, waste_type):
        upcoming = self.get_upcoming_by_type(waste_type)
        return upcoming[0] if upcoming else None

    def get_by_date(self, date, waste_types=None):
        if waste_types:
            return list(filter(lambda x: x.date.date() == date.date() and x.waste_type in waste_types, self.get_sorted()))
        else:
            return list(filter(lambda x: x.date.date() == date.date(), self.get_sorted()))
    
    def get_available_waste_types(self):
        today = datetime.now()
        possible_waste_types = []
        for collection in self.collections:
            if collection.waste_type not in possible_waste_types:
                possible_waste_types.append(collection.waste_type)
        return sorted(possible_waste_types, key=str.lower)


class WasteCollection(object):

    def __init__(self):
        self.date = None
        self.waste_type = None
        self.icon_data = None

    @classmethod
    def create(cls, date, waste_type, icon_data=None):
        collection = cls()
        collection.date = date
        collection.waste_type = waste_type
        collection.icon_data = icon_data
        return collection


class WasteData(object):

    def __init__(self, hass, waste_collector, city_name, postcode, street_name, street_number, suffix, address_id, print_waste_type, update_interval, customer_id):
        self.hass = hass
        self.waste_collector = waste_collector
        self.city_name = city_name
        self.postcode = postcode
        self.street_name = street_name
        self.street_number = street_number
        self.suffix = suffix
        self.address_id = address_id
        self.print_waste_type = print_waste_type
        self.collector = None
        self.update_interval = update_interval
        self.customer_id = customer_id
        self.__select_collector()

    def __select_collector(self):
        if self.waste_collector in XIMMIO_COLLECTOR_IDS.keys():
            self.collector = XimmioCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix, self.address_id, self.customer_id)
        elif self.waste_collector in ["mijnafvalwijzer", "afvalstoffendienstkalender"] or self.waste_collector == "rova":
            self.collector = AfvalwijzerCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "afvalalert":
            self.collector = AfvalAlertCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "deafvalapp":
            self.collector = DeAfvalAppCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "circulus":
            self.collector = CirculusCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "limburg.net":
            self.collector = LimburgNetCollector(self.hass, self.waste_collector, self.city_name, self.postcode, self.street_name, self.street_number, self.suffix)
        elif self.waste_collector == "omrin":
            self.collector = OmrinCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "recycleapp":
            self.collector = RecycleApp(self.hass, self.waste_collector, self.postcode, self.street_name, self.street_number, self.suffix)
        elif self.waste_collector == "rd4":
            self.collector = RD4Collector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector in OPZET_COLLECTOR_URLS.keys():
            self.collector = OpzetCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        else:
            persistent_notification.create(
                self.hass,
                'Waste collector "{}" not found!'.format(self.waste_collector),
                'Afvalwijzer' + " " + self.waste_collector, 
                NOTIFICATION_ID + "_collectornotfound_" + self.waste_collector)

    async def schedule_update(self, interval):
        nxt = dt_util.utcnow() + interval
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)

    async def async_update(self, *_):
        await self.collector.update()
        if self.update_interval != 0:
            await self.schedule_update(timedelta(hours=self.update_interval))
        else:
            await self.schedule_update(SCHEDULE_UPDATE_INTERVAL)
        if self.print_waste_type:
            persistent_notification.create(
                self.hass,
                'Available waste types: ' + ', '.join(self.collector.collections.get_available_waste_types()),
                'Afvalwijzer' + " " + self.waste_collector, 
                NOTIFICATION_ID + "_availablewastetypes_" + self.waste_collector)
            self.print_waste_type = False

    @property
    def collections(self):
        return self.collector.collections


class WasteCollector(metaclass=abc.ABCMeta):

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        self.hass = hass
        self.waste_collector = waste_collector
        self.postcode = postcode
        self.street_number = street_number
        self.suffix = suffix
        self.collections = WasteCollectionRepository()

    @abc.abstractmethod
    async def update(self):
        pass

    def map_waste_type(self, name):
        for from_type, to_type in self.WASTE_TYPE_MAPPING.items():
            if from_type.lower() in name.lower():
                return to_type
        return name.lower()


class AfvalAlertCollector(WasteCollector):
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

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(AfvalAlertCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "https://www.afvalalert.nl/kalender"

    def __get_data(self):
        get_url = '{}/{}/{}{}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

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
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class AfvalwijzerCollector(WasteCollector):
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

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(AfvalwijzerCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.apikey = '5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca'
        if self.waste_collector == "rova":
            self.waste_collector_url = "inzamelkalender." + self.waste_collector
        else:
            self.waste_collector_url = self.waste_collector

    def __get_data(self):
        get_url = 'https://api.{}.nl/webservices/appsinput/?apikey={}&method=postcodecheck&postcode={}&street=&huisnummer={}&toevoeging={}&app_name=afvalwijzer&platform=web&afvaldata={}&langs=nl'.format(
                self.waste_collector_url, self.apikey, self.postcode, self.street_number, self.suffix, datetime.today().strftime('%Y-%m-%d'))
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            data = (response['ophaaldagen']['data'] + response['ophaaldagenNext']['data'])
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
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class CirculusCollector(WasteCollector):
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

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(CirculusCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "https://mijn.circulus.nl"

    def __get_data(self):
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
            if self.suffix != "" and json_response_data["flashMessage"] != "":
                authenticationUrl = ""
                for address in json_response_data["customData"]["addresses"]:
                    if re.search(' '+self.street_number+' '+self.suffix.lower(), address["address"]) != None:
                        authenticationUrl = address["authenticationUrl"]
                        break
                r = requests.get(self.main_url+authenticationUrl, cookies=cookies)

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
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not 'customData' in response or not response['customData']['response']['garbage']:
                _LOGGER.error('No Waste data found!')
                return

            for item in response['customData']['response']['garbage']:
                for date in item['dates']:
                    waste_type = self.map_waste_type(item['code'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                            date=datetime.strptime(date, '%Y-%m-%d'),
                            waste_type=waste_type
                        )
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class DeAfvalAppCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'gemengde plastics': WASTE_TYPE_PLASTIC,
        'zak_blauw': WASTE_TYPE_GREY,
        'pbp': WASTE_TYPE_PACKAGES,
        'rest': WASTE_TYPE_GREY,
        'kerstboom': WASTE_TYPE_TREE
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(DeAfvalAppCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "http://dataservice.deafvalapp.nl"

    def __get_data(self):
        get_url = '{}/dataservice/DataServiceServlet?service=OPHAALSCHEMA&land=NL&postcode={}&straatId=0&huisnr={}&huisnrtoev={}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

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
                        waste_type=waste_type
                    )
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class LimburgNetCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        # 'tak-snoeiafval': WASTE_TYPE_BRANCHES,
        # 'gemengde plastics': WASTE_TYPE_PLASTIC,
        'Grofvuil': WASTE_TYPE_BULKLITTER,
        'Groenafval': WASTE_TYPE_BULKYGARDENWASTE,
        'Tuin- En Snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
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

    def __init__(self, hass, waste_collector, city_name, postcode, street_name, street_number, suffix):
        super(LimburgNetCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.city_name = city_name
        self.street_name = street_name.replace(" ", "+")
        self.main_url = "https://limburg.net/api-proxy/public"
        self.city_id = None
        self.street_id = None

    def __fetch_address(self):
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
        _LOGGER.debug('Updating Waste collection dates using Rest API')

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
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class OmrinCollector(WasteCollector):
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

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(OmrinCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "https://api-omrin.freed.nl/Account"
        self.appId = uuid.uuid1().__str__()
        self.publicKey = None

    def __fetch_publickey(self):
        response = requests.post("{}/GetToken/".format(self.main_url), json={'AppId': self.appId, 'AppVersion': '', 'OsVersion': '', 'Platform': 'HomeAssistant'}).json()
        self.publicKey = b64decode(response['PublicKey'])

    def __get_data(self):
        rsaPublicKey = RSA.importKey(self.publicKey)
        requestBody = {'a': False, 'Email': None, 'Password': None, 'PostalCode': self.postcode, 'HouseNumber': self.street_number}

        encryptedRequest = pkcs1.encrypt(json.dumps(requestBody).encode(), rsaPublicKey)
        base64EncodedRequest = b64encode(encryptedRequest).decode("utf-8")

        response = requests.post("{}/FetchAccount/".format(self.main_url) + self.appId, '"' + base64EncodedRequest + '"', timeout=60).json()
        return response['CalendarV2']

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        try:
            if not self.publicKey:
                await self.hass.async_add_executor_job(self.__fetch_publickey)

            response = await self.hass.async_add_executor_job(self.__get_data)
            self.collections.remove_all()
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
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class OpzetCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'pbd/papier': WASTE_TYPE_PAPER_PMD,
        'snoeiafval': WASTE_TYPE_BRANCHES,
        'sloop': WASTE_TYPE_BULKLITTER,
        'glas': WASTE_TYPE_GLASS,
        'duobak': WASTE_TYPE_GREENGREY,
        'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        'chemisch': WASTE_TYPE_KCA,
        'kca': WASTE_TYPE_KCA,
        'tariefzak restafval': WASTE_TYPE_GREY_BAGS,
        'restafvalzakken': WASTE_TYPE_GREY_BAGS,
        'rest': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstb': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
        'pbd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(OpzetCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = OPZET_COLLECTOR_URLS[self.waste_collector]
        self.bag_id = None
        if waste_collector == "suez":
            self._verify = False
        else:
            self._verify = True

    def __fetch_address(self):
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
        get_url = "{}/rest/adressen/{}/afvalstromen".format(
                self.main_url,
                self.bag_id)
        return requests.get(get_url, verify=self._verify)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

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
                    icon_data=item['icon_data']
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class RD4Collector(WasteCollector):
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

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(RD4Collector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = 'https://data.rd4.nl/api/v1/waste-calendar'
        self.postcode_split = re.search(r"(\d\d\d\d) ?([A-z][A-z])", self.postcode)
        self.postcode = self.postcode_split.group(1) + '+' + self.postcode_split.group(2).upper()

    def __get_data(self):
        self.today = datetime.today()
        self.year = self.today.year
        response = requests.get(
            '{}?postal_code={}&house_number={}&house_number_extension={}&year={}'.format(self.main_url, self.postcode, self.street_number, self.suffix, self.year)
        )
        return response

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

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
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class RecycleApp(WasteCollector):
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

    def __init__(self, hass, waste_collector, postcode, street_name, street_number, suffix):
        super(RecycleApp, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.street_name = street_name
        self.main_url = 'https://api.recycleapp.be/api/app/v1/'
        self.xsecret = '8eTFgy3AQH0mzAcj3xMwaKnNyNnijEFIEegjgNpBHifqtQ4IEyWqmJGFz3ggKQ7B4vwUYS8xz8KwACZihCmboGb6brtVB3rpne2Ww5uUM2n3i4SKNUg6Vp7lhAS8INDUNH8Ll7WPhWRsQOXBCjVz5H8fr0q6fqZCosXdndbNeiNy73FqJBn794qKuUAPTFj8CuAbwI6Wom98g72Px1MPRYHwyrlHUbCijmDmA2zoWikn34LNTUZPd7kS0uuFkibkLxCc1PeOVYVHeh1xVxxwGBsMINWJEUiIBqZt9VybcHpUJTYzureqfund1aeJvmsUjwyOMhLSxj9MLQ07iTbvzQa6vbJdC0hTsqTlndccBRm9lkxzNpzJBPw8VpYSyS3AhaR2U1n4COZaJyFfUQ3LUBzdj5gV8QGVGCHMlvGJM0ThnRKENSWZLVZoHHeCBOkfgzp0xl0qnDtR8eJF0vLkFiKwjX7DImGoA8IjqOYygV3W9i9rIOfK'
        self.xconsumer = 'recycleapp.be'
        self.accessToken = ''
        self.postcode_id = ''
        self.street_id = ''

    def __get_headers(self):
        headers = { 
            'x-secret': self.xsecret,
            'x-consumer': self.xconsumer,
            'User-Agent': '',
            'Authorization': self.accessToken,
        }
        return headers

    def __get_access_token(self):
        response = requests.get("{}access-token".format(self.main_url), headers=self.__get_headers())
        if response.status_code != 200:
            _LOGGER.error('Invalid response from server for accessToken')
            return
        self.accessToken = response.json()['accessToken']
    
    def __get_location_ids(self):
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
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        try:
            if (not self.accessToken):
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
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class XimmioCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'BRANCHES': WASTE_TYPE_BRANCHES,
        'BULKLITTER': WASTE_TYPE_BULKLITTER,
        'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        'GLASS': WASTE_TYPE_GLASS,
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
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, address_id, customer_id):
        super(XimmioCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        if self.waste_collector in self.XIMMIO_URLS.keys():
            self.main_url = self.XIMMIO_URLS[self.waste_collector]
        else:
            self.main_url = "https://wasteapi.ximmio.com"
        self.company_code = XIMMIO_COLLECTOR_IDS[self.waste_collector]
        self.community = ""
        self.customer_id = customer_id
        if address_id:
            self.address_id = address_id
        else:
            self.address_id = None

    def __fetch_address(self):
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
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response['dataList']:
                _LOGGER.error('No Waste data found!')
                return

            for item in response['dataList']:
                for date in item['pickupDates']:
                    waste_type = self.map_waste_type(item['_pickupTypeText'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(date, '%Y-%m-%dT%H:%M:%S'),
                        waste_type=waste_type
                    )
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


def Get_WasteData_From_Config(hass, config):
    _LOGGER.debug("Get Rest API retriever")
    city_name = config.get(CONF_CITY_NAME)
    postcode = config.get(CONF_POSTCODE)
    street_name = config.get(CONF_STREET_NAME)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX)
    address_id = config.get(CONF_ADDRESS_ID)
    waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()

    print_waste_type = config.get(CONF_PRINT_AVAILABLE_WASTE_TYPES)

    update_interval = config.get(CONF_UPDATE_INTERVAL)
    customer_id = config.get(CONF_CUSTOMER_ID)

    config["id"] = _format_id(waste_collector, postcode, street_number)

    if waste_collector in DEPRECATED_AND_NEW_WASTECOLLECTORS:
        persistent_notification.create(
            hass,
            "Update your config to use {}! You are still using {} as a waste collector, which is deprecated. Check your automations and lovelace config, as the sensor names may also be changed!".format(
                DEPRECATED_AND_NEW_WASTECOLLECTORS[waste_collector], waste_collector
            ),
            "Afvalbeheer" + " " + waste_collector,
            NOTIFICATION_ID + "_update_config_" + waste_collector,
        )
        waste_collector = DEPRECATED_AND_NEW_WASTECOLLECTORS[waste_collector]

    if waste_collector in ["limburg.net"] and not city_name:
        persistent_notification.create(
            hass,
            "Config invalid! Cityname is required for {}".format(waste_collector),
            "Afvalbeheer" + " " + waste_collector,
            NOTIFICATION_ID + "_invalid_config_" + waste_collector,
        )
        return

    if waste_collector in ["limburg.net", "recycleapp"] and not street_name:
        persistent_notification.create(
            hass,
            "Config invalid! Streetname is required for {}".format(waste_collector),
            "Afvalbeheer" + " " + waste_collector,
            NOTIFICATION_ID + "_invalid_config_" + waste_collector,
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
        address_id,
        print_waste_type,
        update_interval,
        customer_id,
    )


def _format_id(waste_collector, postcode, house_number):
    return waste_collector + "-" + postcode + "-" + str(house_number)
