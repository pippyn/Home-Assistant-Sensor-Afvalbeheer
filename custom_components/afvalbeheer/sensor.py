import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import CONF_RESOURCES
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from .const import *
from .API import get_wastedata_from_config


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.debug("Setup of sensor platform Afvalbeheer")

    schedule_update = not (discovery_info and "config" in discovery_info)

    config_data = discovery_info["config"] if discovery_info and "config" in discovery_info else config
    data = hass.data[DOMAIN].get(config_data[CONF_ID], None) if not schedule_update else get_wastedata_from_config(hass, config)

    entities = [WasteTypeSensor(data, resource.lower(), config_data) for resource in config_data[CONF_RESOURCES]]
    
    if config_data.get(CONF_UPCOMING):
        entities.extend([WasteDateSensor(data, config_data, timedelta(days=delta)) for delta in (0, 1)])
        entities.append(WasteUpcomingSensor(data, config_data))
    
    async_add_entities(entities)

    if schedule_update: 
        await data.schedule_update(timedelta())


class WasteTypeSensor(RestoreEntity, SensorEntity):

    def __init__(self, data, waste_type, config):
        self.data = data
        self.waste_type = waste_type
        self.waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
        self.date_format = config.get(CONF_DATE_FORMAT)
        self.date_object = config.get(CONF_DATE_OBJECT)
        self.built_in_icons = config.get(CONF_BUILT_IN_ICONS)
        self.built_in_icons_new = config.get(CONF_BUILT_IN_ICONS_NEW)
        self.disable_icons = config.get(CONF_DISABLE_ICONS)
        self.dutch_days = config.get(CONF_TRANSLATE_DAYS)
        self.day_of_week = config.get(CONF_DAY_OF_WEEK)
        self.day_of_week_only = config.get(CONF_DAY_OF_WEEK_ONLY)
        self.always_show_day = config.get(CONF_ALWAYS_SHOW_DAY)
        self.date_only = 1 if self.date_object else config.get(CONF_DATE_ONLY)

        self._today = "Vandaag" if self.dutch_days else "Today"
        self._tomorrow = "Morgen" if self.dutch_days else "Tomorrow"
        
        formatted_name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX),  self.waste_collector, self.waste_type)
        self._name = formatted_name.capitalize()
        self._attr_unique_id = formatted_name
        self._days_until = None
        self._sort_date = 0
        self._hidden = False
        self._entity_picture = None
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def entity_picture(self):
        if self.built_in_icons and not self.disable_icons:
            if self.built_in_icons_new and self.waste_type in FRACTION_ICONS_NEW:
                self._entity_picture = FRACTION_ICONS_NEW[self.waste_type]
            elif self.waste_type in FRACTION_ICONS:
                self._entity_picture = FRACTION_ICONS[self.waste_type]
        return self._entity_picture

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        self._attrs = {
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_HIDDEN: self._hidden,
            ATTR_SORT_DATE: self._sort_date,
            ATTR_DAYS_UNTIL: self._days_until
        }
        return self._attrs

    @property
    def device_class(self):
        if self.date_object:
            return SensorDeviceClass.TIMESTAMP

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        if (state := await self.async_get_last_state()) is None:
            self._state = None
            return

        self._state = state.state

        if ATTR_WASTE_COLLECTOR in state.attributes:
            if not self.disable_icons and 'entity_picture' in state.attributes.keys():
                self._entity_picture = state.attributes['entity_picture']
            self._attrs = {
                ATTR_WASTE_COLLECTOR: state.attributes[ATTR_WASTE_COLLECTOR],
                ATTR_HIDDEN: state.attributes[ATTR_HIDDEN],
                ATTR_SORT_DATE: state.attributes[ATTR_SORT_DATE],
                ATTR_DAYS_UNTIL: state.attributes[ATTR_DAYS_UNTIL]
            }

    def update(self):
        collection = self.data.collections.get_first_upcoming_by_type(self.waste_type)
        if not collection:
            self._state = None
            self._hidden = True
            return

        self._hidden = False
        self.__set_state(collection)
        self.__set_sort_date(collection)
        self.__set_picture(collection)

    def __set_state(self, collection):
        date_diff = (collection.date - datetime.now()).days + 1
        self._days_until = date_diff
        date_format = self.date_format
        if self.date_object:
            self._state = collection.date
        elif self.date_only or (date_diff >= 8 and not self.always_show_day):
            self._state = collection.date.strftime(date_format)
        elif date_diff > 1:
            if self.day_of_week:
                if self.day_of_week_only:
                    date_format = "%A"
                    self._state = collection.date.strftime(date_format)
                else:
                    if "%A"  not in self.date_format:
                        date_format = "%A, " + date_format
                    self._state = collection.date.strftime(date_format)
            else:
                self._state = collection.date.strftime(date_format)
        elif date_diff == 1:
            self._state = collection.date.strftime(self._tomorrow if self.day_of_week_only else self._tomorrow + ", " + date_format)
        elif date_diff == 0:
            self._state = collection.date.strftime(self._today if self.day_of_week_only else self._today + ", " + date_format)
        else:
            self._state = None

        if self.dutch_days and not self.date_object:
            self._state = _translate_state(date_format, self._state)

    def __set_sort_date(self, collection):
        self._sort_date = int(collection.date.strftime('%Y%m%d'))

    def __set_picture(self, collection):
        if collection.icon_data and not self.disable_icons:
            self._entity_picture = collection.icon_data


class WasteDateSensor(RestoreEntity, SensorEntity):

    def __init__(self, data, config, date_delta):
        self.data = data
        self.waste_types = config[CONF_RESOURCES]
        self.waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
        self.dutch_days = config.get(CONF_TRANSLATE_DAYS)
        self.date_delta = date_delta
        if self.date_delta.days == 0:
            day = "vandaag" if self.dutch_days else "today"
        else:
            day = "morgen" if self.dutch_days else "tomorrow"
        formatted_name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX),  self.waste_collector, day)
        self._name = formatted_name.capitalize()
        self._attr_unique_id = formatted_name
        self._hidden = False
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        self._attrs = {
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_HIDDEN: self._hidden
        }
        return self._attrs

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        if (state := await self.async_get_last_state()) is None:
            self._state = None
            return

        self._state = state.state

        if ATTR_WASTE_COLLECTOR in state.attributes:
            self._attrs = {
                ATTR_WASTE_COLLECTOR: state.attributes[ATTR_WASTE_COLLECTOR],
                ATTR_HIDDEN: state.attributes[ATTR_HIDDEN]
            }

    def update(self):
        date = datetime.now() + self.date_delta
        collections = self.data.collections.get_by_date(date, self.waste_types)

        if not collections:
            self._hidden = True
            self._state = "Geen" if self.dutch_days else "None"
            return

        self._hidden = False
        self.__set_state(collections)

    def __set_state(self, collections):
        self._state = ', '.join(set([x.waste_type for x in collections]))


class WasteUpcomingSensor(RestoreEntity, SensorEntity):

    def __init__(self, data, config):
        self.data = data
        self.waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
        self.dutch_days = config.get(CONF_TRANSLATE_DAYS)
        self.date_format = config.get(CONF_DATE_FORMAT)
        self.first_upcoming = "eerst volgende" if self.dutch_days else "first upcoming"
        formatted_name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX),  self.waste_collector, self.first_upcoming)
        self._name = formatted_name.capitalize()
        self._attr_unique_id = formatted_name
        self.upcoming_day = None
        self.upcoming_waste_types = None
        self._hidden = False
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        self._attrs = {
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_UPCOMING_DAY: self.upcoming_day,
            ATTR_UPCOMING_WASTE_TYPES: self.upcoming_waste_types,
            ATTR_HIDDEN: self._hidden
        }
        return self._attrs

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        if (state := await self.async_get_last_state()) is None:
            self._state = None
            return

        self._state = state.state

        if ATTR_WASTE_COLLECTOR in state.attributes:
            self._attrs = {
                ATTR_WASTE_COLLECTOR: state.attributes[ATTR_WASTE_COLLECTOR],
                ATTR_UPCOMING_DAY: state.attributes[ATTR_UPCOMING_DAY],
                ATTR_UPCOMING_WASTE_TYPES: state.attributes[ATTR_UPCOMING_WASTE_TYPES],
                ATTR_HIDDEN: state.attributes[ATTR_HIDDEN]
            }

    def update(self):
        collections = self.data.collections.get_first_upcoming()

        if not collections:
            self._hidden = True
            self._state = "Geen" if self.dutch_days else "None"
            return

        self._hidden = False
        self.__set_state(collections)

    def __set_state(self, collections):
        self.upcoming_day = _translate_state(self.date_format, collections[0].date.strftime(self.date_format))
        self.upcoming_waste_types = ', '.join([x.waste_type for x in collections])
        self._state = self.upcoming_day + ": " + self.upcoming_waste_types


def _format_sensor(name, name_prefix, waste_collector, sensor_type):
    return (
        (waste_collector + ' ' if name_prefix else "") +
        (name + ' ' if name else "") +
        sensor_type
    )


def _translate_state(date_format, state):
    translations = {
        "%B": DUTCH_TRANSLATION_MONTHS,
        "%b": DUTCH_TRANSLATION_MONTHS_SHORT,
        "%A": DUTCH_TRANSLATION_DAYS,
        "%a": DUTCH_TRANSLATION_DAYS_SHORT
    }
    for fmt, trans_dict in translations.items():
        if fmt in date_format:
            for EN_day, NL_day in trans_dict.items():
                state = state.replace(EN_day, NL_day)
    return state
