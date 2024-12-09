import logging
from datetime import datetime, timedelta

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

    entities = [WasteTypeSensor(data, resource, config_data) for resource in config_data[CONF_RESOURCES]]

    if config_data.get(CONF_UPCOMING):
        entities.extend([WasteDateSensor(data, config_data, timedelta(days=delta)) for delta in (0, 1)])
        entities.append(WasteUpcomingSensor(data, config_data))

    async_add_entities(entities)

    if schedule_update:
        await data.schedule_update(timedelta())


class BaseSensor(RestoreEntity, SensorEntity):
    def __init__(self, data, config):
        self.data = data
        self.waste_collector = config.get(CONF_WASTE_COLLECTOR, "").lower()
        self.date_format = config.get(CONF_DATE_FORMAT)
        self.date_object = config.get(CONF_DATE_OBJECT)
        self.built_in_icons = config.get(CONF_BUILT_IN_ICONS)
        self.built_in_icons_new = config.get(CONF_BUILT_IN_ICONS_NEW)
        self.disable_icons = config.get(CONF_DISABLE_ICONS)
        self.dutch_days = config.get(CONF_TRANSLATE_DAYS)
        self.day_of_week = config.get(CONF_DAY_OF_WEEK)
        self.day_of_week_only = config.get(CONF_DAY_OF_WEEK_ONLY)
        self.always_show_day = config.get(CONF_ALWAYS_SHOW_DAY)
        self.waste_types = config[CONF_RESOURCES]
        self.date_only = 1 if self.date_object else config.get(CONF_DATE_ONLY)
        self._hidden = False
        self._state = None
        self._attrs = {}
        self._entity_picture = None
        self._attr_unique_id = None

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    @property
    def entity_picture(self):
        return self._entity_picture

    async def async_added_to_hass(self):
        """Restore the last known state."""
        state = await self.async_get_last_state()
        if state is not None:
            self._state = state.state
            self._restore_attributes(state)
            self._restore_entity_picture(state)

    def _restore_attributes(self, state):
        self._attrs = {
            key: value for key, value in {
                ATTR_WASTE_COLLECTOR: state.attributes.get(ATTR_WASTE_COLLECTOR),
                ATTR_HIDDEN: state.attributes.get(ATTR_HIDDEN),
                ATTR_SORT_DATE: state.attributes.get(ATTR_SORT_DATE),
                ATTR_DAYS_UNTIL: state.attributes.get(ATTR_DAYS_UNTIL),
                ATTR_UPCOMING_DAY: state.attributes.get(ATTR_UPCOMING_DAY),
                ATTR_UPCOMING_WASTE_TYPES: state.attributes.get(ATTR_UPCOMING_WASTE_TYPES),
            }.items() if value is not None
        }

    def _restore_entity_picture(self, state):
        if not self.disable_icons:
            self._entity_picture = state.attributes.get("entity_picture")

    def _translate_state(self, state):
        """Translate state based on format and translation dictionary."""
        translations = {
            "%B": DUTCH_TRANSLATION_MONTHS,
            "%b": DUTCH_TRANSLATION_MONTHS_SHORT,
            "%A": DUTCH_TRANSLATION_DAYS,
            "%a": DUTCH_TRANSLATION_DAYS_SHORT,
        }
        for fmt, trans_dict in translations.items():
            if fmt in self.date_format:
                for en_term, nl_term in trans_dict.items():
                    state = state.replace(en_term, nl_term)
        return state


class WasteTypeSensor(BaseSensor):
    def __init__(self, data, waste_type, config):
        super().__init__(data, config)
        self.waste_type = waste_type
        self._today = "Vandaag" if self.dutch_days else "Today"
        self._tomorrow = "Morgen" if self.dutch_days else "Tomorrow"
        self._name = _format_sensor(
            config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, self.waste_type
        )
        self._attr_unique_id = self._name.lower()
        self._days_until = None
        self._sort_date = 0

    @property
    def name(self):
        return self._name

    @property
    def device_class(self):
        if self.date_object:
            return SensorDeviceClass.TIMESTAMP

    def update(self):
        collection = self.data.collections.get_first_upcoming_by_type(self.waste_type)
        if not collection:
            self._state = None
            self._hidden = True
        else:
            self._hidden = False
            self._set_state(collection)
            self._set_picture(collection)
        self._set_attr(collection)

    def _set_state(self, collection):
        date_diff = (collection.date - datetime.now()).days + 1
        self._days_until = date_diff
        if self.date_object:
            self._state = collection.date
        elif self.date_only or (date_diff >= 8 and not self.always_show_day):
            self._state = collection.date.strftime(self.date_format)
        elif date_diff > 1:
            if self.day_of_week:
                if self.day_of_week_only:
                    self._state = collection.date.strftime("%A")
                else:
                    if "%A"  not in self.date_format:
                        self.date_format = "%A, " + self.date_format
                    self._state = collection.date.strftime(self.date_format)
            else:
                self._state = collection.date.strftime(self.date_format)
        elif date_diff == 1:
            self._state = collection.date.strftime(self._tomorrow if self.day_of_week_only else self._tomorrow + ", " + self.date_format)
        elif date_diff == 0:
            self._state = collection.date.strftime(self._today if self.day_of_week_only else self._today + ", " + self.date_format)
        else:
            self._state = None

        if self.dutch_days and not self.date_object:
            self._state = self._translate_state(self._state)

    def _set_attr(self, collection):
        self._attrs[ATTR_WASTE_COLLECTOR] = self.waste_collector
        self._attrs[ATTR_HIDDEN] = self._hidden
        if collection:
            self._attrs[ATTR_SORT_DATE] = int(collection.date.strftime("%Y%m%d"))
            self._attrs[ATTR_DAYS_UNTIL] = self._days_until

    def _set_picture(self, collection):
        if self.built_in_icons and not self.disable_icons:
            self._entity_picture = self._get_entity_picture()

    def _get_entity_picture(self):
        waste_type_lower = self.waste_type.lower()
        if self.built_in_icons_new and waste_type_lower in FRACTION_ICONS_NEW:
            return FRACTION_ICONS_NEW[waste_type_lower]
        elif waste_type_lower in FRACTION_ICONS:
            return FRACTION_ICONS[waste_type_lower]
        return None


class WasteDateSensor(BaseSensor):
    def __init__(self, data, config, date_delta):
        super().__init__(data, config)
        self.date_delta = date_delta
        if self.date_delta.days == 0:
            day = "vandaag" if self.dutch_days else "today"
        else:
            day = "morgen" if self.dutch_days else "tomorrow"
        self._name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, day)
        self._attr_unique_id = self._name.lower()

    @property
    def name(self):
        return self._name

    def update(self):
        date = datetime.now() + self.date_delta
        collections = self.data.collections.get_by_date(date, self.waste_types)
        if not collections:
            self._hidden = True
            self._state = "Geen" if self.dutch_days else "None"
        else:
            self._hidden = False
            self._state = ", ".join(sorted({x.waste_type for x in collections}))
        self._set_attr()

    def _set_attr(self):
        self._attrs[ATTR_WASTE_COLLECTOR] = self.waste_collector
        self._attrs[ATTR_HIDDEN] = self._hidden


class WasteUpcomingSensor(BaseSensor):
    def __init__(self, data, config):
        super().__init__(data, config)
        self.first_upcoming = "eerstvolgende" if self.dutch_days else "first upcoming"
        self._name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, self.first_upcoming)
        self._attr_unique_id = self._name.lower()
        self.upcoming_day = None
        self.upcoming_waste_types = None

    @property
    def name(self):
        return self._name

    def update(self):
        collections = self.data.collections.get_first_upcoming(self.waste_types)
        if not collections:
            self._hidden = True
            self._state = "Geen" if self.dutch_days else "None"
            return
        else:
            self._hidden = False
            self.upcoming_day = self._translate_state(collections[0].date.strftime(self.date_format))
            self.upcoming_waste_types = ", ".join(sorted([x.waste_type for x in collections]))
            self._state = f"{self.upcoming_day}: {self.upcoming_waste_types}"
        self._set_attr()
    
    def _set_attr(self):
        self._attrs[ATTR_WASTE_COLLECTOR] = self.waste_collector
        self._attrs[ATTR_HIDDEN] = self._hidden
        self._attrs[ATTR_UPCOMING_DAY] = self.upcoming_day
        self._attrs[ATTR_UPCOMING_WASTE_TYPES] = self.upcoming_waste_types


def _format_sensor(name, name_prefix, waste_collector, sensor_type):
    return (
        (waste_collector.capitalize() + " " if name_prefix else "")
        + (name + " " if name else "")
        + sensor_type
    )