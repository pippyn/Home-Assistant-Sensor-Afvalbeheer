import logging
from datetime import datetime
from datetime import timedelta
from typing import Optional, List

from .API import WasteData, get_wastedata_from_config

from homeassistant.config_entries import ConfigEntry

from homeassistant.const import CONF_RESOURCES
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ID

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
    config = dict({**entry.data, **entry.options})

    # CONF_ID should now be provided by config flow
    if CONF_ID not in config:
        _LOGGER.error("Missing CONF_ID in calendar configuration")
        return

    # Always create a new WasteData object with the latest config
    waste_data = get_wastedata_from_config(hass, config)

    if hasattr(waste_data, "async_update"):
        await waste_data.async_update()
    elif hasattr(waste_data, "schedule_update"):
        await waste_data.schedule_update(timedelta())

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

        self._event = None

    @property
    def event(self) -> Optional[CalendarEvent]:
        """
        Get the next upcoming event from the calendar.

        Returns:
            The next CalendarEvent if available, otherwise None.
        """
        if self.WasteData.collections:
            waste_item = self.WasteData.collections.get_sorted()[0]
            return CalendarEvent(
                summary=waste_item.waste_type,
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

        for waste_item in self.WasteData.collections:
            waste_date = waste_item.date.date()
            if start_date.date() <= waste_date <= end_date.date():
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
