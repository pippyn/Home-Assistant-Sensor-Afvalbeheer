"""
Shared collectors that handle multiple municipalities.
"""
from .ximmio import XimmioCollector
from .burgerportaal import BurgerportaalCollector
from .opzet import OpzetCollector
from .klikogroep import KlikogroepCollector

__all__ = ["XimmioCollector", "BurgerportaalCollector", "OpzetCollector", "KlikogroepCollector"]