"""
Omrin collector for waste data from Omrin API.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict
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
        self.refresh_token = None
        self.token_expires_at = None
        self._auth_loaded = False
        self._auth_changed = False
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
            'HouseNumberExtension': self.suffix or None,
            'DeviceId': self.device_id,
            'Platform': 'HomeAssistant',
            'AppVersion': '4.0.0 458',
            'OsVersion': 'HomeAssistant'
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
            self.refresh_token = data['data'].get('refreshToken')
            self._auth_changed = True
            _LOGGER.debug(
                "Omrin login returned access token: %s, refresh token: %s",
                bool(self.token), bool(self.refresh_token)
            )
            expires_at_str = data['data'].get('expiresAt')
            if expires_at_str:
                try:
                    self.token_expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    _LOGGER.debug("Omrin access token expires at %s", self.token_expires_at)
                except (ValueError, TypeError):
                    _LOGGER.warning("Failed to parse token expiration time: %s", expires_at_str)
            return self.token
        else:
            raise Exception(f"Login failed: {data.get('errors', 'Unknown error')}")

    def __refresh_token_request(self) -> str:
        """Refresh the access token using the refresh token"""
        if not self.token or not self.refresh_token:
            raise ValueError("Cannot refresh: missing token or refresh token")
        
        _LOGGER.debug("Refreshing access token")
        
        refresh_data = {
            'Token': self.token,
            'RefreshToken': self.refresh_token
        }
        
        response = self.session.post(
            f"{self.base_url}/api/auth/refreshtoken",
            json=refresh_data
        )
        response.raise_for_status()
        data = response.json()

        if data.get('success') and data.get('data'):
            self.token = data['data'].get('accessToken')
            self.refresh_token = data['data'].get('refreshToken')  # Refresh token rotates
            self._auth_changed = True
            _LOGGER.debug(
                "Omrin refresh returned access token: %s, refresh token: %s",
                bool(self.token), bool(self.refresh_token)
            )
            expires_at_str = data['data'].get('expiresAt')
            if expires_at_str:
                try:
                    self.token_expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    _LOGGER.debug("Refreshed Omrin access token expires at %s", self.token_expires_at)
                except (ValueError, TypeError):
                    _LOGGER.warning("Failed to parse token expiration time: %s", expires_at_str)
            return self.token
        else:
            raise Exception(f"Token refresh failed: {data.get('errors', 'Unknown error')}")

    def __clear_auth_data(self):
        """Clear stale Omrin auth data before logging in again."""
        self.token = None
        self.refresh_token = None
        self.token_expires_at = None
        self._auth_changed = True

    def __ensure_valid_token(self) -> str:
        """Check if token needs refreshing and refresh if necessary"""
        if not self.token:
            raise ValueError("Not logged in")
        
        # Refresh if token expires in less than 1 minute (to be safe)
        if self.token_expires_at:
            time_until_expiry = self.token_expires_at - datetime.now()
            if time_until_expiry.total_seconds() < 60:
                _LOGGER.debug("Token expiring soon, refreshing")
                try:
                    return self.__refresh_token_request()
                except requests.exceptions.HTTPError as exc:
                    if exc.response is None or exc.response.status_code != 401:
                        raise
                    _LOGGER.debug("Stored Omrin refresh token was rejected, logging in again")
                    self.__clear_auth_data()
                    return self.__login()
        
        return self.token

    async def __load_auth_data(self):
        """Load persisted Omrin auth data once per collector instance."""
        if self._auth_loaded:
            return

        data = await self.async_load_auth_data()
        self._auth_loaded = True

        if not data:
            _LOGGER.debug("No stored Omrin auth data found")
            return

        self.device_id = data.get('device_id') or self.device_id
        self.token = data.get('token')
        self.refresh_token = data.get('refresh_token')
        expires_at = data.get('token_expires_at')

        if expires_at:
            try:
                self.token_expires_at = datetime.fromisoformat(expires_at)
                if self.token_expires_at.tzinfo:
                    self.token_expires_at = self.token_expires_at.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError):
                _LOGGER.warning("Failed to parse stored token expiration time: %s", expires_at)

        _LOGGER.debug(
            "Loaded stored Omrin auth data: access token: %s, refresh token: %s, expires at: %s",
            bool(self.token), bool(self.refresh_token), self.token_expires_at
        )

    async def __save_auth_data(self):
        """Persist Omrin auth data when tokens are created or rotated."""
        if not self._auth_changed:
            return

        await self.async_save_auth_data({
            'device_id': self.device_id,
            'token': self.token,
            'refresh_token': self.refresh_token,
            'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
        })
        self._auth_changed = False
        _LOGGER.debug(
            "Saved Omrin auth data: access token: %s, refresh token: %s, expires at: %s",
            bool(self.token), bool(self.refresh_token), self.token_expires_at
        )

    def __graphql_query(self, query: str, retry=True) -> Dict:
        """Execute a GraphQL query"""
        # Ensure token is valid before making the request
        token = self.__ensure_valid_token()

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'GraphQL.Client/6.1.0.0',
            'Authorization': f'Bearer {token}'
        }

        response = self.session.post(
            f"{self.base_url}/graphql",
            headers=headers,
            json={'query': query}
        )

        if response.status_code == 401 and retry:
            _LOGGER.debug("Stored Omrin access token was rejected, logging in again")
            self.__clear_auth_data()
            self.__login()
            return self.__graphql_query(query, retry=False)

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
            await self.__load_auth_data()

            if not self.token:
                _LOGGER.debug("No Omrin access token available, logging in")
                await self.hass.async_add_executor_job(self.__login)
                await self.__save_auth_data()

            response = await self.hass.async_add_executor_job(self.__fetch_calendar)
            await self.__save_auth_data()

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
                    await self.__save_auth_data()
                except Exception as exc:
                    _LOGGER.warning('Failed to fetch diftar data: %r', exc)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False
        except Exception as exc:
            _LOGGER.error('Unexpected error occurred: %r', exc)
            return False
