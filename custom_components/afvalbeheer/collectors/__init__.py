"""
Waste collectors for different APIs.
"""
from .base import WasteCollector
from .shared import XimmioCollector, BurgerportaalCollector, OpzetCollector
from .individual import (
    AfvalAlertCollector, AfvalwijzerCollector, CirculusCollector, CleanprofsCollector,
    DeAfvalAppCollector, LimburgNetCollector, MontferlandNetCollector, OmrinCollector,
    RD4Collector, RecycleApp, ReinisCollector, ROVACollector, StraatbeeldCollector
)

__all__ = [
    "WasteCollector", 
    "XimmioCollector", "BurgerportaalCollector", "OpzetCollector",
    "AfvalAlertCollector", "AfvalwijzerCollector", "CirculusCollector", "CleanprofsCollector",
    "DeAfvalAppCollector", "LimburgNetCollector", "MontferlandNetCollector", "OmrinCollector",
    "RD4Collector", "RecycleApp", "ReinisCollector", "ROVACollector", "StraatbeeldCollector"
]