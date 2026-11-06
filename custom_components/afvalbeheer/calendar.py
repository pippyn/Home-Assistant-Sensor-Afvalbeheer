import logging
from datetime import datetime, time
from datetime import timedelta
from typing import Optional, List

from .API import WasteData, get_wastedata_from_config

from homeassistant.config_entries import ConfigEntry

from homeassistant.const import CONF_RESOURCES
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_ID, CONF_WASTE_COLLECTOR, CONF_ENTRY_ID

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """
    Set up the Afvalbeheer calendar platform.
    """
    schedule_update = not (discovery_info and "config" in discovery_info)
    _LOGGER.debug("Schedule update: %s", schedule_update)

    config_data = discovery_info["config"] if discovery_info and "config" in discovery_info else config

    data = hass.data[DOMAIN].get(config_data[CONF_ID], None) if not schedule_update else get_wastedata_from_config(hass, config)
        
    if hasattr(data, "async_update"):
        await data.async_update()
    elif hasattr(data, "schedule_update"):
        await data.schedule_update(timedelta())

    async_add_entities([AfvalbeheerCalendar(data, config_data)])
    

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    """Set up Afvalbeheer calendar from a config entry."""
    config = dict(hass.data[DOMAIN][entry.entry_id]["config"])
    config[CONF_ENTRY_ID] = entry.entry_id  # Add entry_id to config

    # CONF_ID should now be provided by config flow
    if CONF_ID not in config:
        _LOGGER.error("Missing CONF_ID in calendar configuration")
        return

    waste_data = hass.data[DOMAIN][entry.entry_id]["waste_data"]

    async_add_entities([AfvalbeheerCalendar(waste_data, config)])


class AfvalbeheerCalendar(CalendarEntity):
    """Defines an Afvalbeheer calendar entity."""

    _attr_icon = "mdi:delete-empty"

    def __init__(
        self,
        WasteData: WasteData,
        config,
    ) -> None:
        """
        Initialize the Afvalbeheer calendar entity.

        Args:
            WasteData: The data source for waste collection information.
            config: The platform configuration.
        """
        self.WasteData = WasteData
        self.config = config

        self._attr_name = f"{DOMAIN.capitalize()} {WasteData.waste_collector}"
        self._attr_unique_id = f"{DOMAIN}_{config[CONF_ID]}"
        self.entry_id = config.get(CONF_ENTRY_ID)
        self.waste_collector = config.get(CONF_WASTE_COLLECTOR, "").lower()

        self._event = None

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

    @property
    def event(self) -> Optional[CalendarEvent]:
        """
        Get the next upcoming event from the calendar.

        Returns:
            The next CalendarEvent if available, otherwise None.
        """
        collections = self.WasteData.collections.get_first_upcoming(self.config[CONF_RESOURCES])
        if not collections:
            return None

        waste_item = collections[0]
        return CalendarEvent(
            summary=", ".join(sorted({item.waste_type for item in collections})),
            start=waste_item.date.date(),
            end=(waste_item.date + timedelta(days=1)).date(),
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> List[CalendarEvent]:
        """
        Retrieve calendar events within a specific datetime range.

        Args:
            hass: The Home Assistant instance.
            start_date: The start date for the event range.
            end_date: The end date for the event range.

        Returns:
            A list of CalendarEvent objects within the specified range.
        """
        resources_set = {resource.lower() for resource in self.config[CONF_RESOURCES]}
        events: List[CalendarEvent] = []
        if start_date >= end_date:
            return events

        for waste_item in self.WasteData.collections:
            waste_date = waste_item.date.date()
            event_start = datetime.combine(waste_date, time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            event_end = datetime.combine(waste_date + timedelta(days=1), time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            if event_start < end_date and event_end > start_date:
                if waste_item.waste_type.lower() in resources_set:
                    event = CalendarEvent(
                        summary=waste_item.waste_type,
                        start=waste_date,
                        end=waste_date + timedelta(days=1),
                    )
                    events.append(event)
                    _LOGGER.debug(
                        "Added event: %s on %s", waste_item.waste_type, waste_date
                    )
                else:
                    _LOGGER.debug(
                        "Skipped event: %s (not in configured resources)",
                        waste_item.waste_type,
                    )

        _LOGGER.debug("Total events retrieved: %d", len(events))
        return events
