"""
Shared collectors that handle multiple municipalities.
"""
from .ximmio import XimmioCollector
from .burgerportaal import BurgerportaalCollector
from .opzet import OpzetCollector

__all__ = ["XimmioCollector", "BurgerportaalCollector", "OpzetCollector"]