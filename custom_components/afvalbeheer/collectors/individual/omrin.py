"""
Omrin collector for waste data from Omrin API.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, List
import requests

from ..base import WasteCollector
from ...models import WasteCollection
from ...const import (
    WASTE_TYPE_BULKLITTER, WASTE_TYPE_GREEN, WASTE_TYPE_KCA, WASTE_TYPE_PACKAGES,
    WASTE_TYPE_SORTI, WASTE_TYPE_PAPER, WASTE_TYPE_GREY
)

_LOGGER = logging.getLogger(__name__)


class OmrinCollector(WasteCollector):
    """
    Collector for Omrin waste data.
    """
    WASTE_TYPE_MAPPING = {
        'GFT': WASTE_TYPE_GREEN,
        'PAPIER': WASTE_TYPE_PAPER,
        'PMD': WASTE_TYPE_PACKAGES,
        'RESTAFVAL': WASTE_TYPE_GREY,
        'OVERIG': WASTE_TYPE_KCA,
        'Grofvuil': WASTE_TYPE_BULKLITTER,
        'Grofvuil en elektrische apparaten': WASTE_TYPE_BULKLITTER,
        'Biobak op afroep': WASTE_TYPE_GREEN,
        'Biobak': WASTE_TYPE_GREEN,
        'KCA': WASTE_TYPE_KCA,
        'Chemisch afval': WASTE_TYPE_KCA,
        'Sortibak': WASTE_TYPE_SORTI,
        'Papier': WASTE_TYPE_PAPER,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix, custom_mapping, email=None, password=None):
        super().__init__(hass, waste_collector, postcode, street_number, suffix, custom_mapping)
        self.base_url = "https://api.omrinafvalapp.nl"
        self.device_id = str(uuid.uuid4())
        self.token = None
        self.email = email or None
        self.password = password or None
        self.diftar_data = {}  # Dict of {waste_type: {"dates": [...], "count": int}}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Omrin.Afvalapp.Client/1.0',
            'Accept': 'application/json'
        })

    @property
    def has_credentials(self):
        """Check if user provided login credentials."""
        return bool(self.email and self.password)

    def __login(self) -> str:
        """Login and get JWT token"""
        _LOGGER.debug("Logging in to Omrin API (with credentials: %s)", self.has_credentials)
        
        login_data = {
            'PostalCode': self.postcode,
            'HouseNumber': int(self.street_number) if self.street_number else 0,
            'HouseNumberExtension': self.suffix or '',
            'DeviceId': self.device_id,
            'Platform': 'iOS',
            'AppVersion': '4.0.3.273',
            'OsVersion': 'iPhone15,3 26.2.1'
        }
        
        if self.has_credentials:
            login_data['Email'] = self.email
            login_data['Password'] = self.password
        else:
            login_data['Email'] = None
            login_data['Password'] = None

        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json=login_data
        )
        response.raise_for_status()
        data = response.json()

        if data.get('success') and data.get('data'):
            self.token = data['data'].get('accessToken')
            return self.token
        else:
            raise Exception(f"Login failed: {data.get('errors', 'Unknown error')}")

    def __graphql_query(self, query: str) -> Dict:
        """Execute a GraphQL query"""
        if not self.token:
            raise ValueError("Not logged in")

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'GraphQL.Client/6.1.0.0',
            'Authorization': f'Bearer {self.token}'
        }

        response = self.session.post(
            f"{self.base_url}/graphql",
            headers=headers,
            json={'query': query}
        )
        response.raise_for_status()
        result = response.json()

        if 'errors' in result and result['errors']:
            error_messages = ', '.join([e.get('message', str(e)) for e in result['errors']])
            raise Exception(f"GraphQL error: {error_messages}")

        return result

    def __fetch_calendar(self):
        """Fetch waste collection calendar"""
        _LOGGER.debug("Fetching calendar from Omrin API")
        query = """
        query FetchCalendar {
          fetchCalendar {
            id
            date
            description
            type
            containerType
            placingTime
            state
          }
        }
        """
        result = self.__graphql_query(query)
        return result['data']['fetchCalendar']

    def __fetch_diftar(self):
        """Fetch diftar (emptying history) data from Omrin API"""
        _LOGGER.debug("Fetching diftar data from Omrin API")
        query = """
        query DiftarData {
          diftarData(isDarkTheme: false) {
            totalCount
            fractions {
              type
              count
              totalWeight
              years {
                yearNumber
                count
                totalWeight
                months {
                  monthNumber
                  count
                  totalWeight
                  completedCount
                  weeks {
                    weekNumber
                    count
                    totalWeight
                    days {
                      date
                      status
                      weight
                    }
                  }
                }
              }
            }
          }
        }
        """
        result = self.__graphql_query(query)
        return result['data'].get('diftarData')

    def __parse_diftar_data(self, diftar_response):
        """Parse diftar API response into structured data per waste type."""
        self.diftar_data = {}
        
        if not diftar_response or not diftar_response.get('fractions'):
            _LOGGER.debug("No diftar data available")
            return

        current_year = datetime.now().year

        for fraction in diftar_response['fractions']:
            waste_type_slug = fraction.get('type', '')
            waste_type = self.map_waste_type(waste_type_slug)
            if not waste_type:
                continue

            emptied_dates = []
            total_count = 0
            total_weight = 0.0
            per_year_counts = {}

            for year in fraction.get('years', []):
                year_number = year.get('yearNumber', 0)
                year_count = 0
                for month in year.get('months', []):
                    for week in month.get('weeks', []):
                        for day in week.get('days', []):
                            if day.get('status') == 'COMPLETED':
                                date_str = day.get('date', '')
                                weight = day.get('weight', 0)
                                try:
                                    date = datetime.strptime(date_str, '%Y-%m-%d')
                                    emptied_dates.append(date)
                                    total_count += 1
                                    year_count += 1
                                    total_weight += weight or 0
                                except (ValueError, TypeError):
                                    _LOGGER.warning("Failed to parse diftar date: %s", date_str)
                if year_number and year_count > 0:
                    per_year_counts[year_number] = year_count

            # Sort dates descending (most recent first)
            emptied_dates.sort(reverse=True)

            # Filter for current year
            current_year_dates = [d for d in emptied_dates if d.year == current_year]

            self.diftar_data[waste_type] = {
                'dates': emptied_dates,
                'current_year_dates': current_year_dates,
                'current_year_count': len(current_year_dates),
                'total_count': total_count,
                'total_weight': total_weight,
                'last_emptied': emptied_dates[0] if emptied_dates else None,
                'waste_type_slug': waste_type_slug,
                'per_year_counts': per_year_counts,
            }
            _LOGGER.debug(
                "Diftar %s: %d times emptied this year, last: %s",
                waste_type, len(current_year_dates),
                emptied_dates[0].strftime('%Y-%m-%d') if emptied_dates else 'never'
            )

    async def update(self):
        _LOGGER.debug("Updating Waste collection dates using Omrin API")

        try:
            if not self.token:
                await self.hass.async_add_executor_job(self.__login)

            response = await self.hass.async_add_executor_job(self.__fetch_calendar)

            if not response:
                _LOGGER.error('No Waste data found!')
                return
            
            self.collections.remove_all()

            for item in response:
                if not item.get('date'):
                    continue

                if item['date'] == '0001-01-01T00:00:00':
                    continue

                waste_type = self.map_waste_type(item['type'])
                if not waste_type:
                    _LOGGER.debug(f"Unmapped waste type: {item['type']}")
                    continue

                try:
                    collection_date = datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
                    collection_date = collection_date.replace(tzinfo=None)
                except ValueError as e:
                    _LOGGER.warning(f"Failed to parse date {item['date']}: {e}")
                    continue

                collection = WasteCollection.create(
                    date=collection_date,
                    waste_type=waste_type,
                    waste_type_slug=item['type']
                )
                if collection not in self.collections:
                    self.collections.add(collection)

            _LOGGER.debug(f"Found {len(self.collections)} waste collections")

            # Fetch diftar data if credentials are available
            if self.has_credentials:
                try:
                    diftar_response = await self.hass.async_add_executor_job(self.__fetch_diftar)
                    self.__parse_diftar_data(diftar_response)
                except Exception as exc:
                    _LOGGER.warning('Failed to fetch diftar data: %r', exc)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
        except Exception as exc:
            _LOGGER.error('Unexpected error occurred: %r', exc)
            return False
