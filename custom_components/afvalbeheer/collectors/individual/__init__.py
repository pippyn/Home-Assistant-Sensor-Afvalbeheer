"""
Individual collectors for specific APIs.
"""
from .afval_alert import AfvalAlertCollector
from .afvalwijzer import AfvalwijzerCollector
from .amsterdam import AmsterdamCollector
from .circulus import CirculusCollector
from .cleanprofs import CleanprofsCollector
from .deafvalapp import DeAfvalAppCollector
from .limburg_net import LimburgNetCollector
from .irado import IradoCollector
from .montferland_net import MontferlandNetCollector
from .omrin import OmrinCollector
from .rd4 import RD4Collector
from .recycle_app import RecycleApp
from .reinis import ReinisCollector
from .rova import ROVACollector
from .straatbeeld import StraatbeeldCollector

__all__ = [
    "AfvalAlertCollector", "AfvalwijzerCollector", "AmsterdamCollector", "CirculusCollector", "CleanprofsCollector",
    "DeAfvalAppCollector", "LimburgNetCollector", "IradoCollector", "MontferlandNetCollector", "OmrinCollector",
    "RD4Collector", "RecycleApp", "ReinisCollector", "ROVACollector", "StraatbeeldCollector"
]