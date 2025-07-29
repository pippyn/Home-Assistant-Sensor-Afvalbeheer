"""
Individual collectors for specific APIs.
"""
from .afval_alert import AfvalAlertCollector
from .afvalwijzer import AfvalwijzerCollector
from .circulus import CirculusCollector
from .cleanprofs import CleanprofsCollector
from .deafvalapp import DeAfvalAppCollector
from .limburg_net import LimburgNetCollector
from .montferland_net import MontferlandNetCollector
from .omrin import OmrinCollector
from .rd4 import RD4Collector
from .recycle_app import RecycleApp
from .rova import ROVACollector
from .straatbeeld import StraatbeeldCollector

__all__ = [
    "AfvalAlertCollector", "AfvalwijzerCollector", "CirculusCollector", "CleanprofsCollector",
    "DeAfvalAppCollector", "LimburgNetCollector", "MontferlandNetCollector", "OmrinCollector",
    "RD4Collector", "RecycleApp", "ROVACollector", "StraatbeeldCollector"
]