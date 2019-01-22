"""
Sensor component for waste pickup dates from dutch waste collectors (using the http://www.opzet.nl app)
Original Author: Pippijn Stortelder
Current Version: 2.0.3 20190122 - Pippijn Stortelder
20190116 - Merged different waste collectors into 1 component
20190119 - Added an option to change date format and fixed spelling mistakes
20190122 - Refactor code and bug fix

Description:
  Provides sensors for the following Dutch waste collectors;
  - Blink
  - Cure
  - Cyclus
  - DAR
  - HVC
  - Meerlanden
  - RMN

Save the file as afvalbeheer.py in [homeassistant]/config/custom_components/sensor/

    Main resources options:
    - restafval
    - gft
    - papier
    - pmd
    Some collectors also use some of these options:
    - gftgratis
    - textiel
    - glas
    - grofvuil
    - asbest
    - apparaten
    - chemisch
    - sloopafval
    - takken

Example config:
Configuration.yaml:
  sensor:
    - platform: afvalbeheer
      wastecollector: Blink
      dateformat: '%d-%m-%Y'
      resources:                       (at least 1 required)
        - restafval
        - gft
        - papier
        - pmd
      postcode: 1111AA                 (required)
      streetnumber: 1                  (required)
"""

import logging
from datetime import datetime
from datetime import timedelta
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_RESOURCES)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

__version__ = '2.0.3'

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
CONF_WASTE_COLLECTOR = 'wastecollector'
CONF_POSTCODE = 'postcode'
CONF_STREETNUMBER = 'streetnumber'
CONF_DATE_FORMAT = 'dateformat'

ATTR_OFFICIAL_NAME = 'Official name'
ATTR_WASTE_COLLECTOR = 'wastecollector'
ATTR_FRACTION_ID = 'ID'
ATTR_LAST_UPDATE = 'Last update'
ATTR_HIDDEN = 'Hidden'

COLLECTOR_URL = {
    'blink': 'https://mijnblink.nl',
    'cure': 'https://afvalkalender.cure-afvalbeheer.nl',
    'cyclus': 'https://afvalkalender.cyclusnv.nl',
    'dar': 'https://afvalkalender.dar.nl',
    'hvc': 'https://inzamelkalender.hvcgroep.nl',
    'meerlanden': 'https://afvalkalender.meerlanden.nl',
    'rmn': 'https://inzamelschema.rmn.nl',
}

RENAME_TITLES = {
    'gft gratis': 'gft gratis',
    'groente': 'gft',
    'gft': 'gft',
    'papier': 'papier',
    'rest': 'restafval',
    'plastic': 'pmd',
    'sloop': 'sloopafval',
    'klein chemisch afval': 'kca',
    'kca': 'kca',
    'textiel': 'textiel',
    'kerstbo': 'kerstbomen',
    'snoeiafval': 'snoeiafval',
}

COLLECTOR_WASTE_ID = {}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES, default=[]): cv.ensure_list,
    vol.Required(CONF_POSTCODE, default='1111AA'): cv.string,
    vol.Required(CONF_STREETNUMBER, default='1'): cv.string,
    vol.Optional(CONF_WASTE_COLLECTOR, default='Cure'): cv.string,
    vol.Optional(CONF_DATE_FORMAT, default='%d-%m-%Y'): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.debug('Setup Rest API retriever')

    postcode = config.get(CONF_POSTCODE)
    street_number = config.get(CONF_STREETNUMBER)
    waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
    date_format = config.get(CONF_DATE_FORMAT)

    try:
        data = WasteData(postcode, street_number, waste_collector)
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()
        entities.append(WasteSensor(data, sensor_type, waste_collector, date_format))

    add_entities(entities)


class WasteData(object):

    def __init__(self, postcode, street_number, waste_collector):
        self.data = None
        self.postcode = postcode
        self.street_number = street_number
        self.waste_collector = waste_collector
        self.main_url = COLLECTOR_URL[self.waste_collector]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        try:
            url = self.main_url + '/rest/adressen/' + self.postcode + '-' + self.street_number
            response = requests.get(url).json()

            if not response:
                _LOGGER.error('Address not found!')
            else:
                address_code = response[0]['bagId']
                url = self.main_url + '/rest/adressen/' + address_code + '/afvalstromen'
                request_json = requests.get(url).json()
                if not request_json:
                    _LOGGER.error('No Waste data found!')
                else:
                    COLLECTOR_WASTE_ID[self.waste_collector] = {}
                    sensor_dict = {}

                    for key in request_json:
                        if not key['ophaaldatum'] is None:
                            sensor_dict[str(key['id'])] = [datetime.strptime(key['ophaaldatum'], '%Y-%m-%d'), key['title'], key['title'], key['icon_data']]

                        check_title = key['menu_title']
                        title = ''

                        if not check_title:
                            check_title = key['title'].lower()
                        else:
                            check_title = check_title.lower()

                        for dict_title in RENAME_TITLES:
                            if dict_title in check_title:
                                title = RENAME_TITLES[dict_title]
                                break

                        if not title:
                            title = check_title

                        if title not in COLLECTOR_WASTE_ID[self.waste_collector]:
                            COLLECTOR_WASTE_ID[self.waste_collector][title] = [str(key['id'])]
                        else:
                            COLLECTOR_WASTE_ID[self.waste_collector][title].append(str(key['id']))

                    self.data = sensor_dict

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            self.data = None
            return False


class WasteSensor(Entity):

    def __init__(self, data, sensor_type, waste_collector, date_format):
        self.data = data
        self.type = sensor_type
        self.waste_collector = waste_collector
        self.date_format = date_format
        self._name = waste_collector + ' ' + self.type
        self._unit = ''
        self._hidden = False
        self._entity_picture = None
        self._state = None
        self._official_name = None
        self._fraction_id = None
        self._last_update = None

    @property
    def name(self):
        return self._name

    @property
    def entity_picture(self):
        return self._entity_picture

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        return {
            ATTR_OFFICIAL_NAME: self._official_name,
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_FRACTION_ID: self._fraction_id,
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_HIDDEN: self._hidden
        }

    @property
    def unit_of_measurement(self):
        return self._unit

    def update(self):
        self.data.update()
        waste_data = self.data.data
        retrieved_data = 0
        try:
            if waste_data is not None:
                if self.type in COLLECTOR_WASTE_ID[self.waste_collector]:
                    for waste_id in COLLECTOR_WASTE_ID[self.waste_collector][self.type]:
                        if waste_id in waste_data:
                            today = datetime.today()
                            pickup_info = waste_data.get(waste_id)
                            pick_update = pickup_info[0]
                            datediff = (pick_update - today).days + 1

                            self._official_name = pickup_info[1]
                            self._fraction_id = waste_id
                            self._entity_picture = pickup_info[3]
                            self._last_update = today.strftime('%d-%m-%Y %H:%M')
                            self._hidden = False

                            if datediff >= 8:
                                self._state = pick_update.strftime(self.date_format)
                            elif datediff > 1:
                                self._state = pick_update.strftime('%A, ' + self.date_format)
                            elif datediff == 1:
                                self._state = pick_update.strftime('Tomorrow, ' + self.date_format)
                            elif datediff <= 0:
                                self._state = pick_update.strftime('Today, ' + self.date_format)
                            else:
                                self._state = None
                            retrieved_data = 1

                    if retrieved_data == 0:
                        self._state = None
                        self._official_name = None
                        self._fraction_id = None
                        self._hidden = True
                else:
                    self._state = None
                    self._official_name = None
                    self._fraction_id = None
                    self._hidden = True
            else:
                self._state = None
                self._official_name = None
                self._fraction_id = None
                self._hidden = True

        except ValueError:
            self._state = None
            self._official_name = None
            self._fraction_id = None
            self._hidden = True
