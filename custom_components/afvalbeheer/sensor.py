import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry

from homeassistant.const import CONF_RESOURCES
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import *
from .API import get_wastedata_from_config

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """
    Setup the waste management sensor platform.

    Args:
        hass: Home Assistant object.
        config: Configuration dictionary.
        async_add_entities: Callback to add entities to Home Assistant.
        discovery_info: Discovery information passed by Home Assistant.
    """
    _LOGGER.debug("Setup of sensor platform Afvalbeheer")

    schedule_update = not (discovery_info and "config" in discovery_info)
    _LOGGER.debug("Schedule update: %s", schedule_update)

    config_data = discovery_info["config"] if discovery_info and "config" in discovery_info else config
    _LOGGER.debug("Configuration data: %s", config_data)

    data = hass.data[DOMAIN].get(config_data[CONF_ID], None) if not schedule_update else get_wastedata_from_config(hass, config)
    _LOGGER.debug("Data source: %s", data)

    entities = [WasteTypeSensor(data, resource, config_data) for resource in config_data[CONF_RESOURCES]]
    _LOGGER.debug("Created WasteTypeSensor entities: %s", entities)

    if config_data.get(CONF_UPCOMING):
        entities.extend([WasteDateSensor(data, config_data, timedelta(days=delta)) for delta in (0, 1)])
        entities.append(WasteUpcomingSensor(data, config_data))
        _LOGGER.debug("Added upcoming waste sensors.")

    async_add_entities(entities)
    _LOGGER.debug("Entities added to Home Assistant.")

    if schedule_update:
        _LOGGER.debug("Scheduling data update.")
        await data.schedule_update(timedelta())


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    """Set up Afvalbeheer sensors from a config entry."""
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    config = dict({**entry.data, **entry.options})  # Make a mutable copy
    config[CONF_ENTRY_ID] = entry.entry_id  # Add entry_id to config


    await async_setup_platform(hass, config, async_add_entities)

async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


class BaseSensor(RestoreEntity, SensorEntity):
    """
    Base class for waste management sensors.

    Attributes:
        data: Data source for waste information.
        config: Configuration dictionary for the sensor.
    """
    def __init__(self, data, config):
        self.data = data
        self.waste_collector = config.get(CONF_WASTE_COLLECTOR, "").lower()
        self.entry_id = config.get(CONF_ENTRY_ID)
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
        self._config = config
        _LOGGER.debug("BaseSensor initialized with configuration: %s", config)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        return self._attrs

    @property
    def entity_picture(self):
        """Return the entity picture for the sensor."""
        return self._entity_picture

    @property
    def device_info(self):
        """Return device information for grouping entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry_id)},
            name=f"Afvalbeheer {self.waste_collector.capitalize()}",
            manufacturer="Afvalbeheer",
            model=self.waste_collector.capitalize(),
            entry_type="service",
        )

    async def async_added_to_hass(self):
        """Restore the last known state upon adding to Home Assistant."""
        state = await self.async_get_last_state()
        if state is not None:
            _LOGGER.debug("Restoring last state for sensor: %s", state)
            self._state = state.state
            self._restore_attributes(state)
            self._restore_entity_picture(state)

    def _restore_attributes(self, state):
        """Restore attributes from the previous state."""
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
        _LOGGER.debug("Restored attributes: %s", self._attrs)

    def _restore_entity_picture(self, state):
        """Restore the entity picture from the previous state."""
        if not self.disable_icons:
            self._entity_picture = state.attributes.get("entity_picture")
            _LOGGER.debug("Restored entity picture: %s", self._entity_picture)

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
        _LOGGER.debug("Translated state: %s", state)
        return state


class WasteTypeSensor(BaseSensor):
    """
    Sensor for specific waste types.

    Attributes:
        waste_type: The type of waste this sensor represents.
    """
    def __init__(self, data, waste_type, config):
        super().__init__(data, config)
        self.waste_type = waste_type
        self._today = TODAY_STRING['nl'] if self.dutch_days else TODAY_STRING['en']
        self._tomorrow = TOMORROW_STRING['nl'] if self.dutch_days else TOMORROW_STRING['en']
        self._name = _format_sensor(
            config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, self.waste_type
        )
        self._attr_unique_id = _format_unique_id(
            config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, self.waste_type, self.entry_id, config.get(CONF_POSTCODE), config.get(CONF_STREET_NUMBER)
        ).lower()
        self._days_until = None
        self._sort_date = 0
        _LOGGER.debug("WasteTypeSensor initialized: %s", self._name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class for timestamp sensors."""
        if self.date_object:
            return SensorDeviceClass.TIMESTAMP

    def update(self):
        """Update the state and attributes of the sensor."""
        _LOGGER.debug("Updating WasteTypeSensor: %s", self._name)
        collection = self.data.collections.get_first_upcoming_by_type(self.waste_type)
        if not collection:
            self._state = None
            self._hidden = True
            _LOGGER.debug("No upcoming collection found for waste type: %s", self.waste_type)
        else:
            self._hidden = False
            self._set_state(collection)
            self._set_picture(collection)
        self._set_attr(collection)
        _LOGGER.debug("Updated state for %s: %s", self._name, self._state)

    def _set_state(self, collection):
        """Set the state of the sensor based on collection data."""
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
                    self.date_format = "%A"
                else:
                    if "%A" not in self.date_format:
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
        _LOGGER.debug("State set for %s: %s", self._name, self._state)

    def _set_attr(self, collection):
        """Set the attributes of the sensor based on collection data."""
        self._attrs[ATTR_WASTE_COLLECTOR] = self.waste_collector
        self._attrs[ATTR_HIDDEN] = self._hidden
        if collection:
            self._attrs[ATTR_SORT_DATE] = int(collection.date.strftime("%Y%m%d"))
            self._attrs[ATTR_DAYS_UNTIL] = self._days_until
        _LOGGER.debug("Attributes set for %s: %s", self._name, self._attrs)

    def _set_picture(self, collection):
        """Set the entity picture based on collection data."""
        if (self.built_in_icons or self.built_in_icons_new) and not self.disable_icons:
            self._entity_picture = self._get_entity_picture()
            _LOGGER.debug("Entity picture set for %s: %s", self._name, self._entity_picture)

    def _get_entity_picture(self):
        """Get the appropriate entity picture for the waste type."""
        waste_type_lower = self.waste_type.lower()
        if self.built_in_icons_new and waste_type_lower in FRACTION_ICONS_NEW:
            return FRACTION_ICONS_NEW[waste_type_lower]
        elif self.built_in_icons and waste_type_lower in FRACTION_ICONS:
            return FRACTION_ICONS[waste_type_lower]
        return None


class WasteDateSensor(BaseSensor):
    """
    Sensor for waste collections on specific dates.

    Attributes:
        date_delta: The number of days offset from today.
    """
    def __init__(self, data, config, date_delta):
        super().__init__(data, config)
        self.date_delta = date_delta
        if self.date_delta.days == 0:
            day = TODAY_STRING['nl'].lower() if self.dutch_days else TODAY_STRING['en'].lower()
        else:
            day = TOMORROW_STRING['nl'].lower() if self.dutch_days else TOMORROW_STRING['en'].lower()
        self._name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, day)
        self._attr_unique_id = _format_unique_id(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, day, self.entry_id, config.get(CONF_POSTCODE), config.get(CONF_STREET_NUMBER)).lower()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def update(self):
        """Update the state and attributes of the sensor."""
        date = datetime.now() + self.date_delta
        collections = self.data.collections.get_by_date(date, self.waste_types)
        if not collections:
            self._hidden = True
            self._state = NO_DATE_STRING['nl'] if self.dutch_days else NO_DATE_STRING['en']
        else:
            self._hidden = False
            self._state = ", ".join(sorted({x.waste_type for x in collections}))
        self._set_attr()

    def _set_attr(self):
        """Set the attributes of the sensor."""
        self._attrs[ATTR_WASTE_COLLECTOR] = self.waste_collector
        self._attrs[ATTR_HIDDEN] = self._hidden


class WasteUpcomingSensor(BaseSensor):
    """
    Sensor for the first upcoming waste collection.

    Attributes:
        first_upcoming: Label for the first upcoming waste collection.
    """
    def __init__(self, data, config):
        super().__init__(data, config)
        self.first_upcoming = "eerstvolgende" if self.dutch_days else "first upcoming"
        self._name = _format_sensor(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, self.first_upcoming)
        self._attr_unique_id = _format_unique_id(config.get(CONF_NAME), config.get(CONF_NAME_PREFIX), self.waste_collector, self.first_upcoming, self.entry_id, config.get(CONF_POSTCODE), config.get(CONF_STREET_NUMBER)).lower()
        self.upcoming_day = None
        self.upcoming_waste_types = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def update(self):
        """Update the state and attributes of the sensor."""
        collections = self.data.collections.get_first_upcoming(self.waste_types)
        if not collections:
            self._hidden = True
            self._state = NO_DATE_STRING['nl'] if self.dutch_days else NO_DATE_STRING['en']
            return
        else:
            self._hidden = False
            self.upcoming_day = self._translate_state(collections[0].date.strftime(self.date_format))
            self.upcoming_waste_types = ", ".join(sorted([x.waste_type for x in collections]))
            self._state = f"{self.upcoming_day}: {self.upcoming_waste_types}"
        self._set_attr()
    
    def _set_attr(self):
        """Set the attributes of the sensor."""
        self._attrs[ATTR_WASTE_COLLECTOR] = self.waste_collector
        self._attrs[ATTR_HIDDEN] = self._hidden
        self._attrs[ATTR_UPCOMING_DAY] = self.upcoming_day
        self._attrs[ATTR_UPCOMING_WASTE_TYPES] = self.upcoming_waste_types


def _format_sensor(name, name_prefix, waste_collector, sensor_type):
    """
    Format the sensor name based on its configuration.

    Args:
        name: The base name of the sensor.
        name_prefix: Whether to include the waste collector's name as a prefix.
        waste_collector: Name of the waste collector.
        sensor_type: Type of the sensor (e.g., waste type or date).

    Returns:
        Formatted sensor name as a string.
    """
    return (
        (waste_collector.capitalize() + " " if name_prefix else "")
        + (name + " " if name else "")
        + sensor_type
    )

def _format_unique_id(name, name_prefix, waste_collector, sensor_type, entry_id, postcode=None, street_number=None):
    """
    Format a unique ID for the sensor that is consistent between YAML and Config Flow.

    Args:
        name: The base name of the sensor.
        name_prefix: Whether to include the waste collector's name as a prefix.
        waste_collector: Name of the waste collector.
        sensor_type: Type of the sensor (e.g., waste type or date).
        entry_id: Config entry ID (used for compatibility, but unique ID is based on config values).
        postcode: Postal code for uniqueness (optional).
        street_number: Street number for uniqueness (optional).

    Returns:
        Formatted unique ID as a string.
    """
    parts = [sensor_type]

    if str(waste_collector).lower() == "cleanprofs" or name_prefix:
        parts.insert(0, str(waste_collector))
    if name:
        parts.insert(1, name)
    unique_id = "_".join(parts).replace(" ", "_").replace("-", "_").lower()
    return unique_id
