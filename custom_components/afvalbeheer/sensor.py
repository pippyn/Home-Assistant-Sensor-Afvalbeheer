"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 4.2.1 20200503 - Pippijn Stortelder
20200419 - Major code refactor (credits @basschipper)
20200420 - Add sensor even though not in mapping
20200420 - Added support for DeAfvalApp
20200421 - Fix for OpzetCollector PMD
20200422 - Add wastecollector sudwestfryslan
20200428 - Restore sort_date function
20200428 - Option added to disable daynames (dayofweek)
20200428 - Fixed waste type mapping
20200430 - Fix for the "I/O inside the event loop" warning
20200501 - Fetch address more efficient
20200502 - Support for ACV, Hellendoorn and Twente Milieu
20200503 - Switched Circulus-Berkel to new API
20200503 - Added new Rova API
20200505 - Fix Circulus-Berkel Mapping

Example config:
Configuration.yaml:
sensor:
- platform: afvalbeheer
    wastecollector: Blink            (required)
    resources:                       (at least 1 required)
    - restafval
    - gft
    - papier
    - pmd
    postcode: 1111AA                 (required)
    streetnumber: 1                  (required)
    upcomingsensor: 0                (optional)
    dateformat: '%d-%m-%Y'           (optional)
    dateonly: 0                      (optional)
    dateobject: 0                    (optional)
    dayofweek: 1                     (optional)
    name: ''                         (optional)
    nameprefix: 1                    (optional)
    builtinicons: 0                  (optional)
"""

import abc
import logging
from datetime import datetime
from datetime import timedelta
import json
import random
import requests
import re
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_RESOURCES, DEVICE_CLASS_TIMESTAMP)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

SCHEDULE_UPDATE_INTERVAL = timedelta(hours=1)

CONF_WASTE_COLLECTOR = 'wastecollector'
CONF_POSTCODE = 'postcode'
CONF_STREET_NAME = 'streetname'
CONF_STREET_NUMBER = 'streetnumber'
CONF_SUFFIX = 'suffix'
CONF_DATE_FORMAT = 'dateformat'
CONF_TODAY_TOMORROW = 'upcomingsensor'
CONF_DATE_ONLY = 'dateonly'
CONF_DATE_OBJECT = 'dateobject'
CONF_NAME = 'name'
CONF_NAME_PREFIX = 'nameprefix'
CONF_BUILT_IN_ICONS = 'builtinicons'
CONF_DISABLE_ICONS = 'disableicons'
CONF_TRANSLATE_DAYS = 'dutch'
CONF_DAY_OF_WEEK = 'dayofweek'

ATTR_WASTE_COLLECTOR = 'Wastecollector'
ATTR_HIDDEN = 'Hidden'
ATTR_SORT_DATE = 'Sort-date'

OPZET_COLLECTOR_URLS = {
    'alkmaar': 'https://inzamelkalender.stadswerk072.nl/',
    'alphenaandenrijn': 'https://afvalkalender.alphenaandenrijn.nl',
    'avalex': 'https://www.avalex.nl',
    'berkelland': 'https://afvalkalender.gemeenteberkelland.nl',
    'blink': 'https://mijnblink.nl',
    'cranendonck': 'https://afvalkalender.cranendonck.nl',
    'cyclus': 'https://afvalkalender.cyclusnv.nl',
    'dar': 'https://afvalkalender.dar.nl',
    'denhaag': 'https://huisvuilkalender.denhaag.nl',
    'gad': 'https://inzamelkalender.gad.nl',
    'hvc': 'https://inzamelkalender.hvcgroep.nl',
    'montfoort': 'https://afvalkalender.cyclusnv.nl',
    'peelenmaas': 'https://afvalkalender.peelenmaas.nl',
    'purmerend': 'https://afvalkalender.purmerend.nl',
    'rmn': 'https://inzamelschema.rmn.nl',
    'spaarnelanden': 'https://afvalwijzer.spaarnelanden.nl',
    'sudwestfryslan': 'https://afvalkalender.sudwestfryslan.nl',
    'suez': 'https://inzamelwijzer.suez.nl',
    'venray': 'https://afvalkalender.venray.nl',
    'waalre': 'https://afvalkalender.waalre.nl',
    'zrd': 'https://afvalkalender.zrd.nl',
    'rova': 'https://inzamelkalender.rova.nl',
}

XIMMIO_COLLECTOR_IDS = {
    'acv': 'f8e2844a-095e-48f9-9f98-71fceb51d2c3',
    'hellendoorn': '24434f5b-7244-412b-9306-3a2bd1e22bc1',
    'meerlanden': '800bf8d7-6dd1-4490-ba9d-b419d6dc8a45',
    'twentemilieu': '8d97bb56-5afd-4cbc-a651-b4f7314264b4',
    'ximmio': '800bf8d7-6dd1-4490-ba9d-b419d6dc8a45',
}

WASTE_TYPE_BRANCHES = 'takken'
WASTE_TYPE_BULKLITTER = 'grofvuil'
WASTE_TYPE_GLASS = 'glas'
WASTE_TYPE_GREEN = 'gft'
WASTE_TYPE_GREENGREY = 'duobak'
WASTE_TYPE_GREY = 'restafval'
WASTE_TYPE_KCA = 'chemisch'
WASTE_TYPE_PACKAGES = 'pmd'
WASTE_TYPE_PAPER = 'papier'
WASTE_TYPE_PLASTIC = 'plastic'
WASTE_TYPE_TEXTILE = 'textiel'
WASTE_TYPE_TREE = 'kerstbomen'
WASTE_TYPE_BULKYGARDENWASTE = 'tuinafval'

FRACTION_ICONS = {
    'gft': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzEwOSAyMjQ4YzAsMCAtNTEzLDQzNyAtMTg2LDEwOTMgMTA3LDIxMyAxOTUsMzQ0IDI2NSw0MjQiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE5NzggMzY1MGM4NDMsLTcyOCAtNTksLTE2MzEgLTU5LC0xNjMxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yMzY3IDIxNjBjMCwwIDMyNyw4NjMgLTg3LDE1MTkiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTI5NTQgMzc1MWMtMTU5LC0xNzMgLTUzMiwtNjI5IC00MDEsLTk2OCA3NSwtMTk1IDI4NCwtNDM0IDQwMiwtNTY0Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yOTk1IDIxNzFjLTE1MCwtODIgLTQwNSwtMTYxIC03MDYsMzAgLTExLDAgLTY4OSwtMzcwIC05NDAsLTE5NiAtMjUxLDE3NCAxNzUsLTE5NiAxNzUsLTE5NiAwLDAgNjgxLC00NjYgMTIxNCwtMzkgNyw2IDE0LDEyIDIxLDE4IDExLDAgNjU2LC01MTIgMTE2OSwyMiAtMTEsMCAtNzMyLDY1IC03ODcsNDU3IC00LDQgLTU3LC00NiAtMTQ3LC05NnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE1NjkgMzgxMmMxMzEsMTIwIDQyNiw1NDQgMTAyNyw3NiAwLDAgNDkyLDQ0NiAxMDM4LDEzMCAtMTEsMCAyOTUsLTc2IDQwNCwtNDM1IC03NywzMyAtMjQwLDI1MCAtNjAxLDEyMCAwLDAgLTQwNCwyNjEgLTcyMSwtMTA5IDAsLTIyIC00OTIsMTc0IC02OTksMCAwLC0xMSAtMzE3LDIzOSAtNTc5LC00MyAwLDAgMCwxNDEgMTMxLDI2MXptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzQ3MCAxMDk4YzAsMCAtNzA5LDE0MiAtNjk4LDYzMyAtMTEsMCAtMjI5LC0yNzMgNjExLC04MjlsODcgMTk2em0wIDB6Ii8+DQogPC9nPg0KPC9zdmc+DQo=',
    'gftgratis': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzEwOSAyMjQ4YzAsMCAtNTEzLDQzNyAtMTg2LDEwOTMgMTA3LDIxMyAxOTUsMzQ0IDI2NSw0MjQiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE5NzggMzY1MGM4NDMsLTcyOCAtNTksLTE2MzEgLTU5LC0xNjMxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yMzY3IDIxNjBjMCwwIDMyNyw4NjMgLTg3LDE1MTkiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTI5NTQgMzc1MWMtMTU5LC0xNzMgLTUzMiwtNjI5IC00MDEsLTk2OCA3NSwtMTk1IDI4NCwtNDM0IDQwMiwtNTY0Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yOTk1IDIxNzFjLTE1MCwtODIgLTQwNSwtMTYxIC03MDYsMzAgLTExLDAgLTY4OSwtMzcwIC05NDAsLTE5NiAtMjUxLDE3NCAxNzUsLTE5NiAxNzUsLTE5NiAwLDAgNjgxLC00NjYgMTIxNCwtMzkgNyw2IDE0LDEyIDIxLDE4IDExLDAgNjU2LC01MTIgMTE2OSwyMiAtMTEsMCAtNzMyLDY1IC03ODcsNDU3IC00LDQgLTU3LC00NiAtMTQ3LC05NnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE1NjkgMzgxMmMxMzEsMTIwIDQyNiw1NDQgMTAyNyw3NiAwLDAgNDkyLDQ0NiAxMDM4LDEzMCAtMTEsMCAyOTUsLTc2IDQwNCwtNDM1IC03NywzMyAtMjQwLDI1MCAtNjAxLDEyMCAwLDAgLTQwNCwyNjEgLTcyMSwtMTA5IDAsLTIyIC00OTIsMTc0IC02OTksMCAwLC0xMSAtMzE3LDIzOSAtNTc5LC00MyAwLDAgMCwxNDEgMTMxLDI2MXptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzQ3MCAxMDk4YzAsMCAtNzA5LDE0MiAtNjk4LDYzMyAtMTEsMCAtMjI5LC0yNzMgNjExLC04MjlsODcgMTk2em0wIDB6Ii8+DQogPC9nPg0KPC9zdmc+DQo=',
    'glas': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8bGluZSBjbGFzcz0iZmlsMCBzdHIwIiB4MT0iMjUxNiIgeTE9IjExNzIiIHgyPSIyNzE5IiB5Mj0gIjExNzIiIC8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0zMTUyIDE5OTZjLTcyLC04MCAtMTY1LC0xMDcgLTIyNCwtMTM1IC01OCwtMjcgLTY0LC0xMDAgLTY0LC0xMTcgMCwtMTcgMSwtNTAwIDEsLTUzMyAwLC0zMyAxOCwtNDggMTgsLTQ4IDU0LDAgNjksLTM4IDczLC02MCAyLC05IDIsLTUwIDIsLTUwIDAsLTQyIC0yNywtNzYgLTY5LC03NmwtNDIgLTYzIC00NTIgMCAtNDIgNjNjLTY1LDAgLTcxLDc2IC03MSw3NiAwLDUgMCw0MyAxLDQ3IDcsMzYgNDAsNjMgNzgsNjMgMCwwIDE2LDEyIDE2LDQ4IDAsMzYgMTEsNTE2IDExLDUzMyAwLDE4IC0xMyw4MCAtNzIsMTE5IC01NCwzNiAtMTQzLDYwIC0yMTYsMTMyIC0xNDAsMTM4IC0xMzcsMjk0IC0xMzcsNTAzbDAgMTU2NmMwLDE1MyAxNSwzMTcgMjcwLDMyNyAwLDEgNzY1LC0xIDc2NSwwIDI0MiwtMTUgMjg5LC0xNzYgMjg5LC0zMjdsMCAtMTU2NmMwLC0yMDggMTUsLTMzNSAtMTM3LC01MDN6bTAgMHoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTIyNjcgNDM5M2M1MSwtODIgMjI1LC0xNzUgMzcxLC0xNzUgMTQ2LDAgMjU4LDYzIDM2NSwxNzVsLTczNSAwem0wIDB6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yMjY3IDQzOTNjNTEsLTgyIDIyNSwtMTc1IDM3MSwtMTc1IDE0NiwwIDI1OCw2MyAzNjUsMTc1bC03MzUgMHptMCAweiIvPg0KIDwvZz4NCjwvc3ZnPg0K',
    'papier': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMTMzNiAzNjkwYy05MywyMyAtMTkwLDQ0IC0yOTQsNjJsMTM3OCA4NTBjMCwwIDEwMzgsLTIxIDE5NzMsLTEzNTVsLTIwNCAtMTMxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0xMzkxIDMzNzRjLTExMSwzMiAtMjMxLDYyIC0zNjMsODlsMTM5OCA4MTVjMCwwIDExMTUsLTE4NyAxOTM4LC0xNDA0bC0yMzYgLTEzOSIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMTQzMyAzMzQ5bDkzNyA1MzFjMCwwIDEwMzcsLTYwIDE5MjAsLTE0MjlsLTQ5NiAtMjkxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0xNDk3IDI5MjRjLTE3MCw2NCAtMzI1LDExMiAtNTM1LDE1OGw0NzEgMjY3Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yNDA0IDc3NmMwLDAgMTMsNzA0IC0yNTMsMTExNiAwLDAgLTM5Miw4NjQgLTEyNTYsNjc4bDE0MjggODE0YzQxLDI0IDg2LDQyIDEzMiw1MyAxNTcsMzggNDkyLDY0IDgxMiwtMjc2IDAsMCA1NzEsLTQ1MiA1ODUsLTE1NDJsLTE0NDkgLTg0NHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMjQ1OCA0NjQzYy0zNyw4IDczMywyNCAxOTQ4LC03MTlsLTMzMyAtMjE5YzAsMCAtNTEwLDY4OCAtMTYxNSw5Mzh6bTAgMHoiLz4NCiA8L2c+DQo8L3N2Zz4NCg==',
    'pmd': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zNjExMWluIiBoZWlnaHQ9IjUuMzYxMTFpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTM2MSA1MzYxIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5maWwwIHtmaWxsOiMyMzFGMjA7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI2NzkgMTM4Yy0xNDAxLDAgLTI1NDEsMTE0MCAtMjU0MSwyNTQxIDAsMTQwMSAxMTQwLDI1NDEgMjU0MSwyNTQxIDE0MDEsMCAyNTQxLC0xMTQwIDI1NDEsLTI1NDEgMCwtMTQwMSAtMTE0MCwtMjU0MSAtMjU0MSwtMjU0MXptMCA1MjIwYy0xNDc3LDAgLTI2NzksLTEyMDIgLTI2NzksLTI2NzkgMCwtMTQ3NyAxMjAyLC0yNjc5IDI2NzksLTI2NzkgMTQ3NywwIDI2NzksMTIwMiAyNjc5LDI2NzkgMCwxNDc3IC0xMjAyLDI2NzkgLTI2NzksMjY3OXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0yNzY0IDc3NmMwLDAgMTU4LC0zNCAyODQsNGwtMjg0IC00eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTM3NTcgMjc3N2MwLDAgLTI4MSwtNzUgLTU3NiwybDU3NiAtMnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNzQ4IDQwODZsLTQyIDkyYzAsMCAtMTk2LDYwIC00ODcsLTExbC00MCAtODVjMCwwIDMwNCw5NCA1NjgsNXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0xNzAyIDI0NTVsLTE4MCAtMjY2IDQzMyA4MSAtMjUzIDE4NHptMjk5IC0xNzZjLTUsLTIzIC0yMywtNDAgLTQ2LC00NGwtNDMzIC04MWMtMjMsLTQgLTQ3LDYgLTU5LDI1IC0xMywyMCAtMTMsNDUgMCw2NWwxODAgMjY2YzksMTMgMjMsMjIgMzgsMjUgMywxIDcsMSAxMCwxIDEyLDAgMjQsLTQgMzQsLTExbDI1MyAtMTg0YzE5LC0xNCAyOCwtMzcgMjMsLTYweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI3MzUgMzk0MmM0OSwwIDkzLC04IDkzLC04IDI2LC01IDUyLDkgNjMsMzIgMiwyIDksNSAyMiw1bDggMGM5LDAgMjAsMSAzMiwxIDY1LDAgODYsLTEwIDkwLC0xMyAxMCwtMjEgMzIsLTMzIDU1LC0zMiAxLDAgMjAsMSA0NSwxbC0yMSAxMTZjLTQyLDM5IC0xMTUsNDQgLTE3MCw0NCAtMTMsMCAtMjYsMCAtMzYsLTFsLTggMGMtNDYsLTEgLTc3LC0xNyAtOTYsLTM0IC0yMSwyIC00OSw1IC03OSw1bTU5NyAtMTMxOWM1LC04MiA5LC0xNTcgMTQsLTIxOSA1LC03NiA5LC0xMzcgOSwtMTYyIDAsLTEyIDAsLTI4IDEsLTQ3IDQsLTE1NyAxNCwtNTczIC0xNzMsLTgxNiAtMTUwLC0xOTUgLTE5MiwtMzMzIC0yMDIsLTQxMCAtMTAsMCAtMjEsMCAtMzIsMCAtNDAsMCAtNzYsLTEgLTEwOCwtMyAtMTIsMTAwIC01NSwzMDAgLTIwOCw0ODEgLTY1LDc3IC0xMzcsMjIxIC0xMzQsNDc3bC0xMTYgLTRjLTIsLTI4OSA4NCwtNDU2IDE2MSwtNTQ4IDE4MywtMjE3IDE4NSwtNDY4IDE4NSwtNDcxIDAsLTE3IDcsLTMzIDIwLC00NCAxMywtMTEgMzAsLTE2IDQ3LC0xMyAzNiw2IDg5LDkgMTUyLDkgNDksMCA4NiwtMiA4NiwtMiAxOCwtMSAzNSw3IDQ3LDIwIDEyLDE0IDE3LDMyIDEzLDQ5IDAsMCAtMTYsMTMyIDE4MCwzODggMjExLDI3NSAyMDEsNzIxIDE5Nyw4ODkgMCwxOCAtMSwzMyAtMSw0NCAwLDI5IC00LDg4IC05LDE3MCAtNCw2MiAtOSwxMzYgLTEzLDIxN2wtMTE2IC01eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI4MjIgOTY2YzI5LDcgNjEsMTAgOTMsMTAgMzEsMCA1OCwtMyA3OSwtN2wwIC0xMTljLTU4LDUgLTEyNSwyIC0xNzEsLTNsLTEgMTE5em05MyAxMjZjLTYwLDAgLTExOCwtOSAtMTcxLC0yOCAtMjQsLTggLTM5LC0zMCAtMzksLTU1bDEgLTIzMGMwLC0xOCA4LC0zNCAyMiwtNDUgMTQsLTExIDMyLC0xNSA0OSwtMTEgMSwwIDY2LDE1IDE0OCwxNSA0MiwwIDgwLC00IDExNSwtMTEgMTcsLTQgMzUsMSA0OSwxMiAxNCwxMSAyMiwyOCAyMiw0NWwxIDIzM2MwLDI1IC0xNiw0OCAtNDEsNTYgLTMsMSAtNjcsMjEgLTE1NSwyMXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0yNzY0IDc3NmMwLDAgMTU4LC0zNCAyODQsNGwtMjg0IC00eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTMwNDggODM5Yy02LDAgLTExLC0xIC0xNywtMyAtMTA5LC0zMyAtMjUzLC0zIC0yNTQsLTMgLTMxLDcgLTYyLC0xMyAtNjksLTQ1IC03LC0zMSAxMywtNjIgNDUsLTY5IDcsLTIgMTc1LC0zNyAzMTMsNSAzMSw5IDQ4LDQyIDM4LDczIC04LDI1IC0zMSw0MSAtNTYsNDF6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzE0OSA0MDAxYzQ4LDIzIDE1OCw2NSAzMTMsNjUgMTA1LDAgMjE0LC0xOSAzMjMsLTU3bDAgLTEwNTUgLTUyIC0xMDNjLTU2LDEwIC0xNTcsMjQgLTI4MywyNCAtOTAsMCAtMTc3LC04IC0yNTksLTIybC02MCA5OSAxNyAxMDUwem0zMTMgMTgxYy0yNDcsMCAtMzk2LC05MyAtNDAyLC05NyAtMTcsLTEwIC0yNywtMjkgLTI3LC00OGwtMTggLTExMDFjMCwtMTEgMywtMjIgOCwtMzFsOTAgLTE0OGMxMywtMjEgMzgsLTMyIDYyLC0yNyA4NiwxOCAxNzksMjggMjc2LDI4IDE3MywwIDMwMCwtMzAgMzAxLC0zMCAyNiwtNiA1NCw2IDY2LDMwbDc4IDE1NWM0LDggNiwxNyA2LDI2bDAgMTExMGMwLDI0IC0xNSw0NiAtMzcsNTQgLTEzNiw1MiAtMjcxLDc4IC00MDIsNzh6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzc1NyAyNzc3YzAsMCAtMjgxLC03NSAtNTc2LDJsNTc2IC0yeiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTMxODAgMjgzN2MtMjYsMCAtNDksLTE3IC01NiwtNDMgLTgsLTMxIDEwLC02MyA0MiwtNzEgMzA3LC04MCA1OTQsLTYgNjA2LC0yIDMxLDggNDksNDAgNDEsNzEgLTgsMzEgLTQwLDQ5IC03MSw0MSAtMywtMSAtMjcwLC03MCAtNTQ2LDIgLTUsMSAtMTAsMiAtMTUsMnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNzQ4IDQwODZsLTQyIDkyYzAsMCAtMTk2LDYwIC00ODcsLTExbC00MCAtODVjMCwwIDMwNCw5NCA1NjgsNXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNTAwIDQyNjBjLTk2LDAgLTE5NSwtMTIgLTI5NCwtMzcgLTE3LC00IC0zMSwtMTYgLTM5LC0zMmwtNDAgLTg1Yy0xMCwtMjEgLTYsLTQ1IDksLTYzIDE1LC0xNyAzOSwtMjQgNjEsLTE3IDEsMCAxMzQsNDEgMjk0LDQxIDg4LDAgMTY4LC0xMiAyMzcsLTM2IDIyLC03IDQ2LC0xIDYyLDE2IDE2LDE3IDE5LDQyIDEwLDYzbC00MiA5MmMtNywxNSAtMjAsMjcgLTM2LDMyIC0zLDEgLTg3LDI2IC0yMjQsMjZ6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzQ2MSAzMTAxYy0xMTksMCAtMjYxLC0xNSAtNDE5LC02MCAtMzEsLTkgLTQ5LC00MSAtNDAsLTcyIDksLTMxIDQxLC00OSA3MiwtNDAgNDMyLDEyMyA3MjksMyA3MzIsMiAzMCwtMTIgNjQsMiA3NiwzMSAxMiwzMCAtMiw2NCAtMzEsNzYgLTksNCAtMTU1LDYzIC0zODksNjN6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMTU3NCA0MTQ4bDQyOCA5MiA2MzcgLTE0OSAwIC0xODg3IC02MzggMTE1Yy03LDEgLTEzLDEgLTIwLDBsLTQwNyAtNjkgMCAxODk5em00MjggMjA5Yy00LDAgLTgsMCAtMTIsLTFsLTQ4NiAtMTA0Yy0yNywtNiAtNDYsLTI5IC00NiwtNTdsMCAtMjAxNWMwLC0xNyA4LC0zMyAyMSwtNDQgMTMsLTExIDMwLC0xNiA0NywtMTNsNDY1IDc5IDY5NiAtMTI2YzE3LC0zIDM0LDIgNDgsMTMgMTMsMTEgMjEsMjcgMjEsNDVsMCAyMDAzYzAsMjcgLTE5LDUxIC00NSw1N2wtNjk1IDE2MmMtNCwxIC05LDIgLTEzLDJ6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMTUxNSAyMjM4Yy0yOCwwIC01MiwtMjAgLTU3LC00OCAtNiwtMzIgMTUsLTYyIDQ3LC02OGw2ODggLTEyM2M2LC0xIDEyLC0xIDE4LDBsNDgwIDY5YzMyLDUgNTQsMzQgNDksNjYgLTUsMzIgLTM0LDU0IC02Niw0OWwtNDcxIC02NyAtNjc5IDEyMWMtMywxIC03LDEgLTEwLDF6Ii8+DQogIDxwb2x5Z29uIGNsYXNzPSJmaWwwIiBwb2ludHM9IjE5MzIsNDI5OSAyMDQ4LDQyOTkgMjA0OCwyMjYxIDE5MzIsMjI2MSAiLz4NCiA8L2c+DQo8L3N2Zz4NCg==',
    'pbd': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zNjExMWluIiBoZWlnaHQ9IjUuMzYxMTFpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTM2MSA1MzYxIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5maWwwIHtmaWxsOiMyMzFGMjA7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI2NzkgMTM4Yy0xNDAxLDAgLTI1NDEsMTE0MCAtMjU0MSwyNTQxIDAsMTQwMSAxMTQwLDI1NDEgMjU0MSwyNTQxIDE0MDEsMCAyNTQxLC0xMTQwIDI1NDEsLTI1NDEgMCwtMTQwMSAtMTE0MCwtMjU0MSAtMjU0MSwtMjU0MXptMCA1MjIwYy0xNDc3LDAgLTI2NzksLTEyMDIgLTI2NzksLTI2NzkgMCwtMTQ3NyAxMjAyLC0yNjc5IDI2NzksLTI2NzkgMTQ3NywwIDI2NzksMTIwMiAyNjc5LDI2NzkgMCwxNDc3IC0xMjAyLDI2NzkgLTI2NzksMjY3OXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0yNzY0IDc3NmMwLDAgMTU4LC0zNCAyODQsNGwtMjg0IC00eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTM3NTcgMjc3N2MwLDAgLTI4MSwtNzUgLTU3NiwybDU3NiAtMnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNzQ4IDQwODZsLTQyIDkyYzAsMCAtMTk2LDYwIC00ODcsLTExbC00MCAtODVjMCwwIDMwNCw5NCA1NjgsNXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0xNzAyIDI0NTVsLTE4MCAtMjY2IDQzMyA4MSAtMjUzIDE4NHptMjk5IC0xNzZjLTUsLTIzIC0yMywtNDAgLTQ2LC00NGwtNDMzIC04MWMtMjMsLTQgLTQ3LDYgLTU5LDI1IC0xMywyMCAtMTMsNDUgMCw2NWwxODAgMjY2YzksMTMgMjMsMjIgMzgsMjUgMywxIDcsMSAxMCwxIDEyLDAgMjQsLTQgMzQsLTExbDI1MyAtMTg0YzE5LC0xNCAyOCwtMzcgMjMsLTYweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI3MzUgMzk0MmM0OSwwIDkzLC04IDkzLC04IDI2LC01IDUyLDkgNjMsMzIgMiwyIDksNSAyMiw1bDggMGM5LDAgMjAsMSAzMiwxIDY1LDAgODYsLTEwIDkwLC0xMyAxMCwtMjEgMzIsLTMzIDU1LC0zMiAxLDAgMjAsMSA0NSwxbC0yMSAxMTZjLTQyLDM5IC0xMTUsNDQgLTE3MCw0NCAtMTMsMCAtMjYsMCAtMzYsLTFsLTggMGMtNDYsLTEgLTc3LC0xNyAtOTYsLTM0IC0yMSwyIC00OSw1IC03OSw1bTU5NyAtMTMxOWM1LC04MiA5LC0xNTcgMTQsLTIxOSA1LC03NiA5LC0xMzcgOSwtMTYyIDAsLTEyIDAsLTI4IDEsLTQ3IDQsLTE1NyAxNCwtNTczIC0xNzMsLTgxNiAtMTUwLC0xOTUgLTE5MiwtMzMzIC0yMDIsLTQxMCAtMTAsMCAtMjEsMCAtMzIsMCAtNDAsMCAtNzYsLTEgLTEwOCwtMyAtMTIsMTAwIC01NSwzMDAgLTIwOCw0ODEgLTY1LDc3IC0xMzcsMjIxIC0xMzQsNDc3bC0xMTYgLTRjLTIsLTI4OSA4NCwtNDU2IDE2MSwtNTQ4IDE4MywtMjE3IDE4NSwtNDY4IDE4NSwtNDcxIDAsLTE3IDcsLTMzIDIwLC00NCAxMywtMTEgMzAsLTE2IDQ3LC0xMyAzNiw2IDg5LDkgMTUyLDkgNDksMCA4NiwtMiA4NiwtMiAxOCwtMSAzNSw3IDQ3LDIwIDEyLDE0IDE3LDMyIDEzLDQ5IDAsMCAtMTYsMTMyIDE4MCwzODggMjExLDI3NSAyMDEsNzIxIDE5Nyw4ODkgMCwxOCAtMSwzMyAtMSw0NCAwLDI5IC00LDg4IC05LDE3MCAtNCw2MiAtOSwxMzYgLTEzLDIxN2wtMTE2IC01eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI4MjIgOTY2YzI5LDcgNjEsMTAgOTMsMTAgMzEsMCA1OCwtMyA3OSwtN2wwIC0xMTljLTU4LDUgLTEyNSwyIC0xNzEsLTNsLTEgMTE5em05MyAxMjZjLTYwLDAgLTExOCwtOSAtMTcxLC0yOCAtMjQsLTggLTM5LC0zMCAtMzksLTU1bDEgLTIzMGMwLC0xOCA4LC0zNCAyMiwtNDUgMTQsLTExIDMyLC0xNSA0OSwtMTEgMSwwIDY2LDE1IDE0OCwxNSA0MiwwIDgwLC00IDExNSwtMTEgMTcsLTQgMzUsMSA0OSwxMiAxNCwxMSAyMiwyOCAyMiw0NWwxIDIzM2MwLDI1IC0xNiw0OCAtNDEsNTYgLTMsMSAtNjcsMjEgLTE1NSwyMXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0yNzY0IDc3NmMwLDAgMTU4LC0zNCAyODQsNGwtMjg0IC00eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTMwNDggODM5Yy02LDAgLTExLC0xIC0xNywtMyAtMTA5LC0zMyAtMjUzLC0zIC0yNTQsLTMgLTMxLDcgLTYyLC0xMyAtNjksLTQ1IC03LC0zMSAxMywtNjIgNDUsLTY5IDcsLTIgMTc1LC0zNyAzMTMsNSAzMSw5IDQ4LDQyIDM4LDczIC04LDI1IC0zMSw0MSAtNTYsNDF6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzE0OSA0MDAxYzQ4LDIzIDE1OCw2NSAzMTMsNjUgMTA1LDAgMjE0LC0xOSAzMjMsLTU3bDAgLTEwNTUgLTUyIC0xMDNjLTU2LDEwIC0xNTcsMjQgLTI4MywyNCAtOTAsMCAtMTc3LC04IC0yNTksLTIybC02MCA5OSAxNyAxMDUwem0zMTMgMTgxYy0yNDcsMCAtMzk2LC05MyAtNDAyLC05NyAtMTcsLTEwIC0yNywtMjkgLTI3LC00OGwtMTggLTExMDFjMCwtMTEgMywtMjIgOCwtMzFsOTAgLTE0OGMxMywtMjEgMzgsLTMyIDYyLC0yNyA4NiwxOCAxNzksMjggMjc2LDI4IDE3MywwIDMwMCwtMzAgMzAxLC0zMCAyNiwtNiA1NCw2IDY2LDMwbDc4IDE1NWM0LDggNiwxNyA2LDI2bDAgMTExMGMwLDI0IC0xNSw0NiAtMzcsNTQgLTEzNiw1MiAtMjcxLDc4IC00MDIsNzh6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzc1NyAyNzc3YzAsMCAtMjgxLC03NSAtNTc2LDJsNTc2IC0yeiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTMxODAgMjgzN2MtMjYsMCAtNDksLTE3IC01NiwtNDMgLTgsLTMxIDEwLC02MyA0MiwtNzEgMzA3LC04MCA1OTQsLTYgNjA2LC0yIDMxLDggNDksNDAgNDEsNzEgLTgsMzEgLTQwLDQ5IC03MSw0MSAtMywtMSAtMjcwLC03MCAtNTQ2LDIgLTUsMSAtMTAsMiAtMTUsMnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNzQ4IDQwODZsLTQyIDkyYzAsMCAtMTk2LDYwIC00ODcsLTExbC00MCAtODVjMCwwIDMwNCw5NCA1NjgsNXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNTAwIDQyNjBjLTk2LDAgLTE5NSwtMTIgLTI5NCwtMzcgLTE3LC00IC0zMSwtMTYgLTM5LC0zMmwtNDAgLTg1Yy0xMCwtMjEgLTYsLTQ1IDksLTYzIDE1LC0xNyAzOSwtMjQgNjEsLTE3IDEsMCAxMzQsNDEgMjk0LDQxIDg4LDAgMTY4LC0xMiAyMzcsLTM2IDIyLC03IDQ2LC0xIDYyLDE2IDE2LDE3IDE5LDQyIDEwLDYzbC00MiA5MmMtNywxNSAtMjAsMjcgLTM2LDMyIC0zLDEgLTg3LDI2IC0yMjQsMjZ6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzQ2MSAzMTAxYy0xMTksMCAtMjYxLC0xNSAtNDE5LC02MCAtMzEsLTkgLTQ5LC00MSAtNDAsLTcyIDksLTMxIDQxLC00OSA3MiwtNDAgNDMyLDEyMyA3MjksMyA3MzIsMiAzMCwtMTIgNjQsMiA3NiwzMSAxMiwzMCAtMiw2NCAtMzEsNzYgLTksNCAtMTU1LDYzIC0zODksNjN6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMTU3NCA0MTQ4bDQyOCA5MiA2MzcgLTE0OSAwIC0xODg3IC02MzggMTE1Yy03LDEgLTEzLDEgLTIwLDBsLTQwNyAtNjkgMCAxODk5em00MjggMjA5Yy00LDAgLTgsMCAtMTIsLTFsLTQ4NiAtMTA0Yy0yNywtNiAtNDYsLTI5IC00NiwtNTdsMCAtMjAxNWMwLC0xNyA4LC0zMyAyMSwtNDQgMTMsLTExIDMwLC0xNiA0NywtMTNsNDY1IDc5IDY5NiAtMTI2YzE3LC0zIDM0LDIgNDgsMTMgMTMsMTEgMjEsMjcgMjEsNDVsMCAyMDAzYzAsMjcgLTE5LDUxIC00NSw1N2wtNjk1IDE2MmMtNCwxIC05LDIgLTEzLDJ6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMTUxNSAyMjM4Yy0yOCwwIC01MiwtMjAgLTU3LC00OCAtNiwtMzIgMTUsLTYyIDQ3LC02OGw2ODggLTEyM2M2LC0xIDEyLC0xIDE4LDBsNDgwIDY5YzMyLDUgNTQsMzQgNDksNjYgLTUsMzIgLTM0LDU0IC02Niw0OWwtNDcxIC02NyAtNjc5IDEyMWMtMywxIC03LDEgLTEwLDF6Ii8+DQogIDxwb2x5Z29uIGNsYXNzPSJmaWwwIiBwb2ludHM9IjE5MzIsNDI5OSAyMDQ4LDQyOTkgMjA0OCwyMjYxIDE5MzIsMjI2MSAiLz4NCiA8L2c+DQo8L3N2Zz4NCg==',
    'restafval': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNDUyNCA0MjQxYzQ4LC0zOTggMTksLTU1OCAtMTM4LC04MDMgLTE1NiwtMjQ1IC0xMDczLC0xMzEyIC0xMDczLC0xMzEybDM5MSAxMDA5IC01MjYgLTg0NiAtMjAzIDExMzUgLTExIC0xMTU0IC05MDEgNDMyIDk1MSAtNjQxIDMzOSA3NCAxMDEzIC01NDIgLTY5NSAtMTU2IC0yNzcgNDc3IDg3IC0xMDMzIC02ODkgNjAxIDEzNyAtMjM3IC01OTYgLTMwOSA0NTEgOTQzIC0xOTc0IDkyMyAtMjE3IDUyMyAyMTYgNTIwIC0xNjEgLTY3IC0xNTEgMzQwbTM5ODMgNDIxYzIwLC0xMjcgMzUsLTIzMSA0MywtMjk5Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik01Mjc1IDI2NjVjMCwxNDQxIC0xMTY4LDI2MTAgLTI2MTAsMjYxMCAtMTQ0MSwwIC0yNjEwLC0xMTY4IC0yNjEwLC0yNjEwIDAsLTE0NDEgMTE2OCwtMjYxMCAyNjEwLC0yNjEwIDE0NDEsMCAyNjEwLDExNjggMjYxMCwyNjEwem0wIDB6Ii8+DQogPC9nPg0KPC9zdmc+DQo=',
}

DUTCH_TRANSLATION_DAYS = {
    'Monday': 'Maandag',
    'Tuesday': 'Dinsdag',
    'Wednesday': 'Woensdag',
    'Thursday': 'Donderdag',
    'Friday': 'Vrijdag',
    'Saturday': 'Zaterdag',
    'Sunday': 'Zondag'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES, default=[]): cv.ensure_list,
    vol.Required(CONF_POSTCODE, default='1111AA'): cv.string,
    vol.Required(CONF_STREET_NAME, default=''): cv.string,
    vol.Required(CONF_STREET_NUMBER, default='1'): cv.string,
    vol.Optional(CONF_SUFFIX, default=''): cv.string,
    vol.Optional(CONF_WASTE_COLLECTOR, default='Cure'): cv.string,
    vol.Optional(CONF_DATE_FORMAT, default='%d-%m-%Y'): cv.string,
    vol.Optional(CONF_TODAY_TOMORROW, default=False): cv.boolean,
    vol.Optional(CONF_DATE_ONLY, default=False): cv.boolean,
    vol.Optional(CONF_DATE_OBJECT, default=False): cv.boolean,
    vol.Optional(CONF_NAME, default=''): cv.string,
    vol.Optional(CONF_NAME_PREFIX, default=True): cv.boolean,
    vol.Optional(CONF_BUILT_IN_ICONS, default=False): cv.boolean,
    vol.Optional(CONF_DISABLE_ICONS, default=False): cv.boolean,
    vol.Optional(CONF_TRANSLATE_DAYS, default=False): cv.boolean,
    vol.Optional(CONF_DAY_OF_WEEK, default=True): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.debug('Setup Rest API retriever')

    postcode = config.get(CONF_POSTCODE)
    street_name = config.get(CONF_STREET_NAME)
    street_number = config.get(CONF_STREET_NUMBER)
    suffix = config.get(CONF_SUFFIX)
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

    if date_object == True:
        date_only = 1
    else:
        date_only = config.get(CONF_DATE_ONLY)

    if waste_collector == "cure":
        _LOGGER.error("Afvalbeheer - Update your config to use Mijnafvalwijzer! You are still using Cure as a wast collector, which is deprecated. It's from now on; Mijnafvalwijzer. Check your automations and lovelace config, as the sensor names may also be changed!")
        waste_collector = "mijnafvalwijzer"
    elif waste_collector == "ximmio":
        _LOGGER.error("Ximmio - due to more collectors using Ximmio, you need to change your config. Set the wast collector to the actual collector (i.e. Meerlanden, TwenteMilieu , etc.). Using Ximmio in your config, this sensor will asume you meant Meerlanden.")

    data = WasteData(hass, waste_collector, postcode, street_name, street_number, suffix)

    entities = []

    for resource in config[CONF_RESOURCES]:
        waste_type = resource.lower()
        entities.append(WasteTypeSensor(data, waste_type, waste_collector, date_format, date_only, date_object, name, name_prefix, built_in_icons, disable_icons, dutch_days, day_of_week))

    if sensor_today:
        entities.append(WasteDateSensor(data, config[CONF_RESOURCES], waste_collector, timedelta(), dutch_days, name, name_prefix))
        entities.append(WasteDateSensor(data, config[CONF_RESOURCES], waste_collector, timedelta(days=1), dutch_days, name, name_prefix))

    async_add_entities(entities)

    await data.schedule_update(timedelta())


class WasteCollectionRepository(object):

    def __init__(self):
        self.collections = []

    def add(self, collection):
        self.collections.append(collection)

    def remove_all(self):
        self.collections = []

    def get_sorted(self):
        return sorted(self.collections, key=lambda x: x.date)

    def get_upcoming_by_type(self, waste_type):
        today = datetime.now()
        return list(filter(lambda x: x.date.date() >= today.date() and x.waste_type == waste_type, self.get_sorted()))

    def get_first_upcoming_by_type(self, waste_type):
        upcoming = self.get_upcoming_by_type(waste_type)
        return upcoming[0] if upcoming else None

    def get_by_date(self, date, waste_types=None):
        if waste_types:
            return list(filter(lambda x: x.date.date() == date.date() and x.waste_type in waste_types, self.get_sorted()))
        else:
            return list(filter(lambda x: x.date.date() == date.date(), self.get_sorted()))


class WasteCollection(object):

    def __init__(self):
        self.date = None
        self.waste_type = None
        self.icon_data = None

    @classmethod
    def create(cls, date, waste_type, icon_data=None):
        collection = cls()
        collection.date = date
        collection.waste_type = waste_type
        collection.icon_data = icon_data
        return collection


class WasteData(object):

    def __init__(self, hass, waste_collector, postcode, street_name, street_number, suffix):
        self.hass = hass
        self.waste_collector = waste_collector
        self.postcode = postcode
        self.street_name = street_name
        self.street_number = street_number
        self.suffix = suffix
        self.collector = None
        self.__select_collector()

    def __select_collector(self):
        if self.waste_collector in XIMMIO_COLLECTOR_IDS.keys():
            self.collector = XimmioCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector in ["mijnafvalwijzer", "afvalstoffendienstkalender"]:
            self.collector = AfvalwijzerCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "deafvalapp":
            self.collector = DeAfvalAppCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "circulus-berkel":
            self.collector = CirculusBerkelCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector == "ophaalkalender":
            self.collector = OphaalkalenderCollector(self.hass, self.waste_collector, self.postcode, self.street_name, self.street_number, self.suffix)
        elif self.waste_collector == "rova":
            self.collector = RovaCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        elif self.waste_collector in OPZET_COLLECTOR_URLS.keys():
            self.collector = OpzetCollector(self.hass, self.waste_collector, self.postcode, self.street_number, self.suffix)
        else:
            _LOGGER.error('Waste collector "{}" not found!'.format(self.waste_collector))

    async def schedule_update(self, interval):
        nxt = dt_util.utcnow() + interval
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)

    async def async_update(self, *_):
        await self.collector.update()
        await self.schedule_update(SCHEDULE_UPDATE_INTERVAL)

    @property
    def collections(self):
        return self.collector.collections


class WasteCollector(metaclass=abc.ABCMeta):

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        self.hass = hass
        self.waste_collector = waste_collector
        self.postcode = postcode
        self.street_number = street_number
        self.suffix = suffix
        self.collections = WasteCollectionRepository()

    @abc.abstractmethod
    async def update(self):
        pass

    def map_waste_type(self, name):
        for from_type, to_type in self.WASTE_TYPE_MAPPING.items():
            if from_type.lower() in name.lower():
                return to_type
        return name.lower()


class AfvalwijzerCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'takken': WASTE_TYPE_BRANCHES,
        'grofvuil': WASTE_TYPE_BULKLITTER,
        'tuinafval': WASTE_TYPE_BULKYGARDENWASTE,
        'glas': WASTE_TYPE_GLASS,
        'gft': WASTE_TYPE_GREEN,
        'kca': WASTE_TYPE_KCA,
        'restafval': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstbomen': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(AfvalwijzerCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)

    def __get_data(self):
        get_url = 'https://json.{}.nl/?method=postcodecheck&postcode={}&street=&huisnummer={}&toevoeging={}&langs=nl'.format(
                self.waste_collector, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            data = (response['data']['ophaaldagen']['data'] + response['data']['ophaaldagenNext']['data'])

            if not data:
                _LOGGER.error('No Waste data found!')
                return

            for item in data:
                if not item['date']:
                    continue

                waste_type = self.map_waste_type(item['type'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['date'], '%Y-%m-%d'),
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class CirculusBerkelCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        # 'BRANCHES': WASTE_TYPE_BRANCHES,
        # 'BULKLITTER': WASTE_TYPE_BULKLITTER,
        # 'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        # 'GLASS': WASTE_TYPE_GLASS,
        'GFT': WASTE_TYPE_GREEN,
        'RESTAFR': WASTE_TYPE_GREY,
        # 'KCA': WASTE_TYPE_KCA,
        'ZWAKRA': WASTE_TYPE_PACKAGES,
        'PMD': WASTE_TYPE_PACKAGES,
        'PAP': WASTE_TYPE_PAPER,
        # 'TEXTILE': WASTE_TYPE_TEXTILE,
        # 'TREE': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(CirculusBerkelCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "https://mijn.circulus-berkel.nl"

    def __get_data(self):
        r = requests.get(self.main_url)
        cookies = r.cookies

        for item in cookies.items():
            if item[0] == "CB_SESSION":
                session_cookie = item[1]

        if session_cookie:
            authenticityToken = re.search('__AT=(.*)&___TS=', session_cookie).group(1)
            data = { 
                'authenticityToken': authenticityToken,
                'zipCode': self.postcode,
                'number': self.street_number,
                } 

            r = requests.post(
                '{}/register/zipcode.json'.format(self.main_url), data=data, cookies=cookies
            )
            logged_in_cookies = r.cookies
        else:
            _LOGGER.error("Unable to get Session Cookie")

        if logged_in_cookies:
            startDate = (datetime.today() - timedelta(days=14)).strftime("%Y-%m-%d")
            endDate =  (datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d")
            
            headers = { 
                'Content-Type': 'application/json'
            }

            response = requests.get('{}/afvalkalender.json?from={}&till={}'.format(
                self.main_url, 
                startDate, 
                endDate
                ), headers=headers, cookies=logged_in_cookies)
            return response
        else:
            _LOGGER.error("Unable to get Logged-in Cookie")

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response['customData']['response']['garbage']:
                _LOGGER.error('No Waste data found!')
                return

            for item in response['customData']['response']['garbage']:
                for date in item['dates']:
                    waste_type = self.map_waste_type(item['code'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                            date=datetime.strptime(date, '%Y-%m-%d'),
                            waste_type=waste_type
                        )
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class DeAfvalAppCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'gemengde plastics': WASTE_TYPE_PLASTIC,
        'zak_blauw': WASTE_TYPE_GREY,
        'pbp': WASTE_TYPE_PACKAGES,
        'rest': WASTE_TYPE_GREY,
        'kerstboom': WASTE_TYPE_TREE
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(DeAfvalAppCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "http://dataservice.deafvalapp.nl"

    def __get_data(self):
        get_url = '{}/dataservice/DataServiceServlet?service=OPHAALSCHEMA&land=NL&postcode={}&straatId=0&huisnr={}&huisnrtoev={}'.format(
                self.main_url, self.postcode, self.street_number, self.suffix)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.text

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for rows in response.strip().split('\n'):
                waste_type = self.map_waste_type(rows.split(';')[0])
                if not waste_type:
                    continue

                for ophaaldatum in rows.split(';')[1:-1]:
                    if not ophaaldatum:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(ophaaldatum, '%d-%m-%Y'),
                        waste_type=waste_type
                    )
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class OphaalkalenderCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        # 'tak-snoeiafval': WASTE_TYPE_BRANCHES,
        'gemengde plastics': WASTE_TYPE_PLASTIC,
        'grof huisvuil': WASTE_TYPE_BULKLITTER,
        'grof huisvuil afroep': WASTE_TYPE_BULKLITTER,
        # 'tak-snoeiafval': WASTE_TYPE_BULKYGARDENWASTE,
        # 'fles-groen-glas': WASTE_TYPE_GLASS,
        'tuinafval': WASTE_TYPE_GREEN,
        # 'batterij': WASTE_TYPE_KCA,
        'restafval': WASTE_TYPE_GREY,
        'pmd': WASTE_TYPE_PACKAGES,
        'p-k': WASTE_TYPE_PAPER,
        # 'shirt-textiel': WASTE_TYPE_TEXTILE,
        # 'kerstboom': WASTE_TYPE_TREE,
        'gemengde plastics': WASTE_TYPE_PLASTIC,
    }

    def __init__(self, hass, waste_collector, postcode, street_name, street_number, suffix):
        super(OphaalkalenderCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.street_name = street_name
        self.main_url = "https://www.ophaalkalender.be"
        self.address_id = None

    def __fetch_address(self):
        response = requests.get('{}/calendar/findstreets/?query={}&zipcode={}'.format(
            self.main_url, self.street_name, self.postcode)).json()

        if not response:
            _LOGGER.error('Address not found!')
            return

        self.address_id = str(response[0]["Id"])

    def __get_data(self):
        get_url = '{}/api/rides?id={}&housenumber={}&zipcode={}'.format(
                self.main_url, self.address_id, self.street_number, self.postcode)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['start']:
                    continue

                waste_type = self.map_waste_type(item['title'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['start'], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None),
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class OpzetCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'snoeiafval': WASTE_TYPE_BRANCHES,
        'sloop': WASTE_TYPE_BULKLITTER,
        'glas': WASTE_TYPE_GLASS,
        'duobak': WASTE_TYPE_GREENGREY,
        'groente': WASTE_TYPE_GREEN,
        'gft': WASTE_TYPE_GREEN,
        'chemisch': WASTE_TYPE_KCA,
        'kca': WASTE_TYPE_KCA,
        'rest': WASTE_TYPE_GREY,
        'plastic': WASTE_TYPE_PACKAGES,
        'papier': WASTE_TYPE_PAPER,
        'textiel': WASTE_TYPE_TEXTILE,
        'kerstb': WASTE_TYPE_TREE,
        'pmd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(OpzetCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = OPZET_COLLECTOR_URLS[self.waste_collector]
        self.bag_id = None

    def __fetch_address(self):
        response = requests.get(
            "{}/rest/adressen/{}-{}".format(self.main_url, self.postcode, self.street_number)).json()

        if not response:
            _LOGGER.error('Address not found!')
            return

        self.bag_id = response[0]['bagId']

    def __get_data(self):
        get_url = "{}/rest/adressen/{}/afvalstromen".format(
                self.main_url,
                self.bag_id)
        return requests.get(get_url)

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            if not self.bag_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['ophaaldatum']:
                    continue

                waste_type = self.map_waste_type(item['menu_title'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item['ophaaldatum'], '%Y-%m-%d'),
                    waste_type=waste_type,
                    icon_data=item['icon_data']
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class RovaCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        # 'snoeiafval': WASTE_TYPE_BRANCHES,
        # 'sloop': WASTE_TYPE_BULKLITTER,
        # 'glas': WASTE_TYPE_GLASS,
        # 'duobak': WASTE_TYPE_GREENGREY,
        # 'groente': WASTE_TYPE_GREEN,
        # 'gft': WASTE_TYPE_GREEN,
        # 'chemisch': WASTE_TYPE_KCA,
        # 'kca': WASTE_TYPE_KCA,
        # 'rest': WASTE_TYPE_GREY,
        # 'plastic': WASTE_TYPE_PACKAGES,
        # 'papier': WASTE_TYPE_PAPER,
        # 'textiel': WASTE_TYPE_TEXTILE,
        # 'kerstb': WASTE_TYPE_TREE,
        # 'pmd': WASTE_TYPE_PACKAGES,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(RovaCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = 'https://www.rova.nl'
        self.rova_id = random.randint(10000, 30000)

    def __get_data(self):
        response = requests.get(
            '{}/api/TrashCalendar/GetCalendarItems'.format(self.main_url), params={'portal': 'inwoners'}, 
            cookies=self.__get_cookies()
            )
        return response

    def __get_cookies(self):
        return {'RovaLc_inwoners': "{{'Id':{},'ZipCode':'{}', \
        'HouseNumber':'{}', 'HouseAddition':'{}','Municipality':'', \
        'Province':'', 'Firstname':'','Lastname':'','UserAgent':'', \
        'School':'', 'Street':'','Country':'','Portal':'', \
        'Lat':'','Lng':'', 'AreaLevel':'','City':'','Ip':''}}"
        .format(self.rova_id, self.postcode, self.street_number, self.suffix)}

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            r = await self.hass.async_add_executor_job(self.__get_data)
            response = json.loads(r.text)

            if not response:
                _LOGGER.error('No Waste data found!')
                return

            for item in response:
                if not item['Date']:
                    continue

                waste_type = self.map_waste_type(item['GarbageTypeCode'])
                if not waste_type:
                    continue

                collection = WasteCollection.create(
                    date=datetime.strptime(item["Date"], "%Y-%m-%dT%H:%M:%S"),
                    waste_type=waste_type
                )
                self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class XimmioCollector(WasteCollector):
    WASTE_TYPE_MAPPING = {
        'BRANCHES': WASTE_TYPE_BRANCHES,
        'BULKLITTER': WASTE_TYPE_BULKLITTER,
        'BULKYGARDENWASTE': WASTE_TYPE_BULKYGARDENWASTE,
        'GLASS': WASTE_TYPE_GLASS,
        'GREEN': WASTE_TYPE_GREEN,
        'GREY': WASTE_TYPE_GREY,
        'KCA': WASTE_TYPE_KCA,
        'PACKAGES': WASTE_TYPE_PACKAGES,
        'PAPER': WASTE_TYPE_PAPER,
        'TEXTILE': WASTE_TYPE_TEXTILE,
        'TREE': WASTE_TYPE_TREE,
    }

    def __init__(self, hass, waste_collector, postcode, street_number, suffix):
        super(XimmioCollector, self).__init__(hass, waste_collector, postcode, street_number, suffix)
        self.main_url = "https://wasteapi.ximmio.com"
        self.company_code = XIMMIO_COLLECTOR_IDS[self.waste_collector]
        self.address_id = None

    def __fetch_address(self):
        data = {
            "postCode": self.postcode,
            "houseNumber": self.street_number,
            "companyCode": self.company_code
        }
        response = requests.post(
            "{}/api/FetchAdress".format(self.main_url),
            data=data).json()

        if not response['dataList']:
            _LOGGER.error('Address not found!')
            return

        self.address_id = response['dataList'][0]['UniqueId']

    def __get_data(self):
        data = {
            "uniqueAddressID": self.address_id,
            "startDate": datetime.now().strftime('%Y-%m-%d'),
            "endDate": (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
            "companyCode": self.company_code,
        }
        response = requests.post(
            "{}/api/GetCalendar".format(self.main_url),
            data=data)
        return response

    async def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        self.collections.remove_all()

        try:
            if not self.address_id:
                await self.hass.async_add_executor_job(self.__fetch_address)

            r = await self.hass.async_add_executor_job(self.__get_data)
            response = r.json()

            if not response['dataList']:
                _LOGGER.error('No Waste data found!')
                return

            for item in response['dataList']:
                for date in item['pickupDates']:
                    waste_type = self.map_waste_type(item['_pickupTypeText'])
                    if not waste_type:
                        continue

                    collection = WasteCollection.create(
                        date=datetime.strptime(date, '%Y-%m-%dT%H:%M:%S'),
                        waste_type=waste_type
                    )
                    self.collections.add(collection)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            return False


class WasteTypeSensor(Entity):

    def __init__(self, data, waste_type, waste_collector, date_format, date_only, date_object, name, name_prefix, built_in_icons, disable_icons, dutch_days, day_of_week):
        self.data = data
        self.waste_type = waste_type
        self.waste_collector = waste_collector
        self.date_format = date_format
        self.date_only = date_only
        self.date_object = date_object
        self._name = _format_sensor(name, name_prefix, waste_collector, self.waste_type)
        self.built_in_icons = built_in_icons
        self.disable_icons = disable_icons
        self.dutch_days = dutch_days
        self.day_of_week = day_of_week
        if self.dutch_days:
            self._today = "Vandaag, "
            self._tomorrow = "Morgen, "
        else:
            self._today = "Today, "
            self._tomorrow = "Tomorrow, "
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
    def device_state_attributes(self):
        return {
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_HIDDEN: self._hidden,
            ATTR_SORT_DATE: self._sort_date
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

        if self.date_object:
            self._state = collection.date
        elif self.date_only:
            self._state = collection.date.strftime(self.date_format)
        elif date_diff >= 8:
            self._state = collection.date.strftime(self.date_format)
        elif date_diff > 1:
            if self.day_of_week:
                self._state = collection.date.strftime('%A, ' + self.date_format)
                if self.dutch_days:
                    for EN_day, NL_day in DUTCH_TRANSLATION_DAYS.items():
                        self._state = self._state.replace(EN_day, NL_day)
            else:
                self._state = collection.date.strftime(self.date_format)
        elif date_diff == 1:
            self._state = collection.date.strftime(self._tomorrow + self.date_format)
        elif date_diff == 0:
            self._state = collection.date.strftime(self._today + self.date_format)
        else:
            self._state = None

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
            day = 'vandaag'
        elif date_delta.days == 1:
            day = 'morgen'
        else:
            day = ''
        self._name = _format_sensor(name, name_prefix, waste_collector, day)
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
    def device_state_attributes(self):
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
