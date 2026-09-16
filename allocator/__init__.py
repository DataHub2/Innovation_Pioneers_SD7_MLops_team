"""Allocation component: distributes local solar energy by need and criticality.

Core principle: need is broken down into *loads*, each load sits on a *tier* of
a load ladder, and the tiers are filled from the bottom up. A load on a higher
tier can never take energy from a load on a lower tier.
"""

from .config import Config, DEFAULT_CONFIG
from .models import (
    Alloc,
    AllocRequest,
    AllocResult,
    Category,
    Load,
    Property,
    PropertyHistory,
    ReasonCode,
    Tier,
    TIER_ORDER,
)
from .policy import TieredNeedPolicy

__all__ = [
    "Alloc",
    "AllocRequest",
    "AllocResult",
    "Category",
    "Config",
    "DEFAULT_CONFIG",
    "Load",
    "Property",
    "PropertyHistory",
    "ReasonCode",
    "Tier",
    "TIER_ORDER",
    "TieredNeedPolicy",
]

__version__ = "0.2.0"
