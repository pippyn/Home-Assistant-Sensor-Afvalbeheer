import logging
from datetime import datetime
from datetime import timedelta
from typing import Optional, List

from .API import WasteData

from homeassistant.const import CONF_RESOURCES
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ID


_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, async_add_entities, discovery_info=None):

    if discovery_info and "config" in discovery_info:
        conf = discovery_info["config"]
    else:
        conf = config

    if not conf:
        return

    async_add_entities([AfvalbeheerCalendar(hass.data[DOMAIN][conf[CONF_ID]], conf)])


class AfvalbeheerCalendar(CalendarEntity):
    """Defines a Afvalbeheer calendar."""

    _attr_icon = "mdi:delete-empty"

    def __init__(
        self,
        WasteData: WasteData,
        config,
    ) -> None:
        """Initialize the Afvalbeheer entity."""
        self.WasteData = WasteData
        self.config = config

        self._attr_name = f"{DOMAIN.capitalize()} {WasteData.waste_collector}"
        self._attr_unique_id = f"{DOMAIN}_{config[CONF_ID]}"

        self._event = None

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event."""
        if len(self.WasteData.collections) > 0:
            waste_item = self.WasteData.collections.get_sorted()[0]
            return CalendarEvent(
                summary=waste_item.waste_type,
                start=waste_item.date.date(),
                end=(waste_item.date + timedelta(days=1)).date(),
            )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> List[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events: List[CalendarEvent] = []
        for waste_items in self.WasteData.collections:
            if start_date.date() <= waste_items.date.date() <= end_date.date():
                # Summary below will define the name of event in calendar
                if waste_items.waste_type in self.config[CONF_RESOURCES]:
                    events.append(
                        CalendarEvent(
                            summary=waste_items.waste_type,
                            start=waste_items.date.date(),
                            end=waste_items.date.date(),
                        )
                    )

        return events
