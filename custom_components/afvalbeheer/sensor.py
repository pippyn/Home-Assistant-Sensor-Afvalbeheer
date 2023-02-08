import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import CONF_RESOURCES
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from .const import *
from .API import Get_WasteData_From_Config


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.debug("Setup of sensor platform Afvalbeheer")

    schedule_update = False

    if discovery_info and "config" in discovery_info:
        config = discovery_info["config"]
        data = hass.data[DOMAIN].get(config[CONF_ID], None)
    else:
        schedule_update = True
        data = Get_WasteData_From_Config(hass, config)

    waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
    date_format = config.get(CONF_DATE_FORMAT)
    sensor_today = config.get(CONF_TODAY_TOMORROW)
    date_object = config.get(CONF_DATE_OBJECT)
    name = config.get(CONF_NAME)
    name_prefix = config.get(CONF_NAME_PREFIX)
    built_in_icons = config.get(CONF_BUILT_IN_ICONS)
    built_in_icons_new = config.get(CONF_BUILT_IN_ICONS_NEW)
    disable_icons = config.get(CONF_DISABLE_ICONS)
    dutch_days = config.get(CONF_TRANSLATE_DAYS)
    day_of_week = config.get(CONF_DAY_OF_WEEK)
    day_of_week_only = config.get(CONF_DAY_OF_WEEK_ONLY)
    always_show_day = config.get(CONF_ALWAYS_SHOW_DAY)

    if date_object == True:
        date_only = 1
    else:
        date_only = config.get(CONF_DATE_ONLY)

    entities = []

    for resource in config[CONF_RESOURCES]:
        waste_type = resource.lower()
        entities.append(
            WasteTypeSensor(
                data,
                waste_type,
                waste_collector,
                date_format,
                date_only,
                date_object,
                name,
                name_prefix,
                built_in_icons,
                built_in_icons_new,
                disable_icons,
                dutch_days,
                day_of_week,
                day_of_week_only,
                always_show_day,
            )
        )

    if sensor_today:
        entities.append(
            WasteDateSensor(
                data,
                config[CONF_RESOURCES],
                waste_collector,
                timedelta(),
                dutch_days,
                name,
                name_prefix,
            )
        )
        entities.append(
            WasteDateSensor(
                data,
                config[CONF_RESOURCES],
                waste_collector,
                timedelta(days=1),
                dutch_days,
                name,
                name_prefix,
            )
        )

    async_add_entities(entities)

    if schedule_update: 
        await data.schedule_update(timedelta())


class WasteTypeSensor(RestoreEntity, SensorEntity):

    def __init__(self, data, waste_type, waste_collector, date_format, date_only, date_object,
                name, name_prefix, built_in_icons, built_in_icons_new,disable_icons, dutch_days, 
                day_of_week, day_of_week_only, always_show_day):
        self.data = data
        self.waste_type = waste_type
        self.waste_collector = waste_collector
        self.date_format = date_format
        self.date_only = date_only
        self.date_object = date_object
        self._name = _format_sensor(name, name_prefix, waste_collector, self.waste_type)
        self._attr_unique_id = _format_sensor(name, name_prefix, waste_collector, self.waste_type)
        self.built_in_icons = built_in_icons
        self.built_in_icons_new = built_in_icons_new
        self.disable_icons = disable_icons
        self.dutch_days = dutch_days
        self.day_of_week = day_of_week
        self.day_of_week_only = day_of_week_only
        self.always_show_day = always_show_day
        if self.dutch_days:
            self._today = "Vandaag"
            self._tomorrow = "Morgen"
        else:
            self._today = "Today"
            self._tomorrow = "Tomorrow"
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
        if self.date_object == True:
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
        elif self.date_only:
            self._state = collection.date.strftime(date_format)
        elif date_diff >= 8 and not self.always_show_day:
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
            if self.day_of_week_only:
                self._state = collection.date.strftime(self._tomorrow)
            else:
                self._state = collection.date.strftime(self._tomorrow + ", " + date_format)
        elif date_diff == 0:
            if self.day_of_week_only:
                self._state = collection.date.strftime(self._today)
            else:
                self._state = collection.date.strftime(self._today + ", " + date_format)
        else:
            self._state = None

        if self.dutch_days and not self.date_object:
            if "%B" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_MONTHS.items():
                    self._state = self._state.replace(EN_day, NL_day)
            if "%b" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_MONTHS_SHORT.items():
                    self._state = self._state.replace(EN_day, NL_day)
            if "%A" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_DAYS.items():
                    self._state = self._state.replace(EN_day, NL_day)
            if "%a" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_DAYS_SHORT.items():
                    self._state = self._state.replace(EN_day, NL_day)

    def __set_sort_date(self, collection):
        self._sort_date = int(collection.date.strftime('%Y%m%d'))

    def __set_picture(self, collection):
        if collection.icon_data and not self.disable_icons:
            self._entity_picture = collection.icon_data


class WasteDateSensor(RestoreEntity, SensorEntity):

    def __init__(self, data, waste_types, waste_collector, date_delta, dutch_days, name, name_prefix):
        self.data = data
        self.waste_types = waste_types
        self.waste_collector = waste_collector
        self.date_delta = date_delta
        self.dutch_days = dutch_days
        if date_delta.days == 0:
            day = 'vandaag' if self.dutch_days else "today"
        elif date_delta.days == 1:
            day = 'morgen' if self.dutch_days else "tomorrow"
        else:
            day = ''
        self._name = _format_sensor(name, name_prefix, waste_collector, day)
        self._attr_unique_id = _format_sensor(name, name_prefix, waste_collector, day)
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
            ATTR_HIDDEN: self._hidden
        }
        return self._attrs

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        if (state := await self.async_get_last_state()) is None:
            self._state = None
            return

        self._state = state.state

        if ATTR_HIDDEN in state.attributes:
            self._attrs = {
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
        self._state = ', '.join([x.waste_type for x in collections])


def _format_sensor(name, name_prefix, waste_collector, sensor_type):
    return (
        (waste_collector + ' ' if name_prefix else "") +
        (name + ' ' if name else "") +
        sensor_type
    )
