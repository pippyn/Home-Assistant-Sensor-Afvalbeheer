import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import CONF_RESOURCES, DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity

from .const import *
from .API import Get_WasteData_From_Config


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    # Without breaking existing config to load using sensor as component you get a direct call with the config to here.
    # sensor:
    #   platform: afvalbeheer
    #   ....
    # This function could be simplified and non async function when depricating this way of accessing.
    # New way of the config should be:
    # Afvalbeheer:
    #   ....

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


class WasteTypeSensor(Entity):

    def __init__(self, data, waste_type, waste_collector, date_format, date_only, date_object,
                name, name_prefix, built_in_icons, disable_icons, dutch_days, day_of_week,
                day_of_week_only, always_show_day):
        self.data = data
        self.waste_type = waste_type
        self.waste_collector = waste_collector
        self.date_format = date_format
        self.date_only = date_only
        self.date_object = date_object
        self._name = _format_sensor(name, name_prefix, waste_collector, self.waste_type)
        self._attr_unique_id = _format_sensor(name, name_prefix, waste_collector, self.waste_type)
        self.built_in_icons = built_in_icons
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
        self._unit = ''
        self._sort_date = 0
        self._hidden = False
        self._entity_picture = None
        self._state = None

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
    def extra_state_attributes(self):
        return {
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_HIDDEN: self._hidden,
            ATTR_SORT_DATE: self._sort_date,
            ATTR_DAYS_UNTIL: self._days_until
        }

    @property
    def device_class(self):
        if self.date_object == True:
            return DEVICE_CLASS_TIMESTAMP

    @property
    def unit_of_measurement(self):
        return self._unit

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
            if "%b" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_MONTHS_SHORT.items():
                    self._state = self._state.replace(EN_day, NL_day)
            if "%B" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_MONTHS.items():
                    self._state = self._state.replace(EN_day, NL_day)
            if "%A" in date_format:
                for EN_day, NL_day in DUTCH_TRANSLATION_DAYS.items():
                    self._state = self._state.replace(EN_day, NL_day)

    def __set_sort_date(self, collection):
        self._sort_date = int(collection.date.strftime('%Y%m%d'))

    def __set_picture(self, collection):
        if self.disable_icons:
            return

        if self.built_in_icons and self.waste_type in FRACTION_ICONS:
            self._entity_picture = FRACTION_ICONS[self.waste_type]
        elif collection.icon_data:
            self._entity_picture = collection.icon_data


class WasteDateSensor(Entity):

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
        self._unit = ''
        self._hidden = False
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            ATTR_HIDDEN: self._hidden
        }

    @property
    def unit_of_measurement(self):
        return self._unit

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
