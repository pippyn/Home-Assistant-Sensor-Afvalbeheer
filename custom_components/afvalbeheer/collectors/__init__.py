"""
Waste collectors for different APIs.
"""
from .base import WasteCollector
from .shared import XimmioCollector, BurgerportaalCollector, OpzetCollector, KlikogroepCollector
from .individual import (
    AfvalAlertCollector, AfvalwijzerCollector, AmsterdamCollector, CirculusCollector, CleanprofsCollector,
    DeAfvalAppCollector, LimburgNetCollector, IradoCollector, MontferlandNetCollector, OmrinCollector,
    RD4Collector, RecycleApp, ReinisCollector, ROVACollector, StraatbeeldCollector
)

__all__ = [
    "WasteCollector",
    "XimmioCollector", "BurgerportaalCollector", "OpzetCollector", "KlikogroepCollector",
    "AfvalAlertCollector", "AfvalwijzerCollector", "AmsterdamCollector", "CirculusCollector", "CleanprofsCollector",
    "DeAfvalAppCollector", "LimburgNetCollector", "IradoCollector", "MontferlandNetCollector", "OmrinCollector",
    "RD4Collector", "RecycleApp", "ReinisCollector", "ROVACollector", "StraatbeeldCollector"
]