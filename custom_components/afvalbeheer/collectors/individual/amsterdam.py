"""
Amsterdam collector for waste data from Amsterdam API.
"""
import logging
from datetime import datetime
import requests
from datetime import timedelta

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BULKLITTER, WASTE_TYPE_GREEN, WASTE_TYPE_GREY, 
    WASTE_TYPE_PAPER, WASTE_TYPE_TEXTILE, WASTE_TYPE_GLASS, 
    WASTE_TYPE_PMD_GREY
)

_LOGGER = logging.getLogger(__name__)


class AmsterdamCollector(WasteCollector):
    """
    Collector for Amsterdam waste data.
    """
    WASTE_TYPE_MAPPING = {
        'ga': WASTE_TYPE_BULKLITTER,
        'glas': WASTE_TYPE_GLASS,
        'gft': WASTE_TYPE_GREEN,
        'rest': WASTE_TYPE_GREY,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'plastic': WASTE_TYPE_PMD_GREY,
    }
    
    WEEKDAY_MAP = {
        'maandag': 1,
        'dinsdag': 2,
        'woensdag': 3,
        'donderdag': 4,
        'vrijdag': 5,
        'zaterdag': 6,
        'zondag': 7
    }

    def date_in_future(self, dates_list, current_date):
        """Filter dates that are in the future."""
        return [date for date in dates_list if date > current_date]

    def generate_dates_for_year(self, day_delta, week_interval, current_date, even_weeks = False):
        dates = []
        week_offset = 0
        while week_offset <= 52:
            date = (current_date + timedelta(days=day_delta, weeks=week_offset))
            if week_interval > 1:
                # IF statement to account for 52week years vs 53week years
                if ((date.isocalendar()[1]%2 == 0) and not even_weeks) or ((date.isocalendar()[1]%2 > 0) and even_weeks):
                    date = date - timedelta(weeks=1)
                    if dates[(len(dates)-1)] == date:
                        date = (date + timedelta(weeks=2))
                        week_offset = week_offset + 1
                    elif ((date.isocalendar()[1]%2 > 0) and even_weeks):
                        date = (date + timedelta(weeks=2))
                        week_offset = week_offset + 2
                    else:
                        week_offset = week_offset - 1
            dates.append(date)
            week_offset = week_offset + week_interval
        return dates
    
    def check_response_for_suffix(self, params):
        """Check if API response is valid for given parameters."""
        filtered_params = {k: v for k, v in params.items() if v}
        query_string = '&'.join(f'{k}={v}' for k, v in filtered_params.items())
        get_url = f'{self.waste_collector_url}/?{query_string}'
        test_response = requests.get(get_url)
        is_valid = len(test_response.text) > 220
        return is_valid, get_url

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.waste_collector_url = "https://api.data.amsterdam.nl/v1/afvalwijzer/afvalwijzer"

    def __get_data(self):
        """Fetch waste collection data from API."""
        # Define suffix parameter variations to try
        suffix_params = []
        if self.suffix:
            suffix_params = [
                {'huisletter': self.suffix.lower()},
                {'huisnummertoevoeging': self.suffix.lower()},
                {'huisletter': self.suffix.upper()},
                {'huisnummertoevoeging': self.suffix.upper()}
            ]
        
        # Base parameters
        base_params = {
            'postcode': self.postcode,
            'huisnummer': self.street_number
        }
        
        # Try each suffix combination
        for suffix_param in suffix_params:
            params = {**base_params, **suffix_param}
            test_result, get_url = self.check_response_for_suffix(params)
            if test_result:
                return requests.get(get_url)
        
        # No suffix or all suffix attempts failed - use base parameters
        filtered_params = {k: v for k, v in base_params.items() if v}
        query_string = '&'.join(f'{k}={v}' for k, v in filtered_params.items())
        get_url = f'{self.waste_collector_url}/?{query_string}'
        return requests.get(get_url)

    def _parse_date(self, date_str, today):
        """Parse date string with multiple format attempts."""
        date_formats = ['%d-%m-%y', '%d-%m-%Y', '%d-%m']
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # If format is day-month only, add current year
                if fmt == '%d-%m':
                    parsed_date = datetime(today.year, parsed_date.month, parsed_date.day)
                return parsed_date
            except ValueError:
                continue
        
        _LOGGER.error('Unable to process date: %s', date_str)
        return None

    def _calculate_day_delta(self, week_day, today, frequency_type=None):
        """Calculate day delta for collection day calculation."""
        current_iso = today.isocalendar()
        current_week = current_iso[1]
        current_weekday = current_iso[2]
        is_even_week = current_week % 2 == 0
        
        if frequency_type == 'oneven':  # Odd weeks
            if is_even_week:
                return (week_day - current_weekday) + 7
            elif current_weekday > week_day:
                return (week_day - current_weekday) + 14
            else:
                return week_day - current_weekday
        elif frequency_type == 'even':  # Even weeks
            if not is_even_week:
                return (week_day - current_weekday) + 7
            elif current_weekday > week_day:
                return (week_day - current_weekday) + 14
            else:
                return week_day - current_weekday
        else:  # Weekly
            if current_weekday > week_day:
                return (week_day - current_weekday) + 7
            else:
                return week_day - current_weekday

    def _is_item_valid(self, item):
        """Validate waste collection item has required fields."""
        if not item['afvalwijzerAfvalkalenderFrequentie'] and not item['afvalwijzerWaar']:
            return False
        if not item['afvalwijzerAfvalkalenderFrequentie'] and 'stoep' not in item['afvalwijzerWaar']:
            return False
        if not item['afvalwijzerFractieCode'] or not item['afvalwijzerOphaaldagen']:
            return False
        return True

    def _process_collection_dates(self, item, today):
        """Process and calculate collection dates for an item."""
        collection_days = item['afvalwijzerOphaaldagen'].replace(' ', '').split(',')
        future_dates = []
        
        for day in collection_days:
            week_day = self.WEEKDAY_MAP.get(day)
            if not week_day:
                continue
                
            frequency = item['afvalwijzerAfvalkalenderFrequentie']
            
            if not frequency:
                # Weekly collection
                day_delta = self._calculate_day_delta(week_day, today)
                future_dates.extend(self.generate_dates_for_year(day_delta, 1, today, False))
            elif 'weken' in frequency or 'week' in frequency:
                # Bi-weekly collection (odd/even weeks)
                frequency_clean = frequency.replace(' weken', '').replace(' week', '')
                day_delta = self._calculate_day_delta(week_day, today, frequency_clean)
                is_even = frequency_clean == 'even'
                future_dates.extend(self.generate_dates_for_year(day_delta, 2, today, is_even))
            else:
                # Specific dates provided
                date_strings = frequency.replace(' ', '.').replace('./', '').replace('.', ',').split(',')
                dates = []
                for date_str in date_strings:
                    parsed_date = self._parse_date(date_str, today)
                    if parsed_date:
                        dates.append(parsed_date)
                future_dates.extend(self.date_in_future(dates, today))
        
        return future_dates

    async def update(self):
        """Update waste collection dates using Rest API."""
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if len(response['_embedded']['afvalwijzer']) < 1:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()
            today = datetime.now()

            for item in response['_embedded']['afvalwijzer']:
                if not self._is_item_valid(item):
                    continue

                waste_type = self.map_waste_type(item['afvalwijzerFractieCode'].lower())
                if not waste_type:
                    continue
                
                future_dates = self._process_collection_dates(item, today)
                    
                for date in future_dates:
                    collection = WasteCollection.create(
                        date=date.replace(hour=0, minute=0, second=0, microsecond=0),
                        waste_type=waste_type,
                        waste_type_slug=item['afvalwijzerFractieCode'].lower()
                    )
                    if collection not in self.collections:
                        self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False