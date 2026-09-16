"""Data models for the allocation component.

Design notes worth knowing:

* Allocation is driven by the **tier of the load**, never by the category of the
  building. A clinic can have a tier-1 load (vaccine cold chain) and a tier-4
  load (air conditioning). A household can have a tier-1 load (home dialysis)
  and a tier-4 load (TV). There is therefore no "property weight" anywhere in
  the model.
* No clock, no I/O, no hidden state. Time and history arrive as parameters, so
  the component is deterministic and testable without a simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Mapping

EPS = 1e-9


class Category(str, Enum):
    """Metadata about the property. Used for reporting and for default tier
    assignment only — never to rank one property against another."""

    CLINIC = "clinic"
    WATER = "water"
    SCHOOL = "school"
    PRODUCTIVE = "productive"
    HOUSEHOLD = "household"
    COMMUNITY = "community"


class Tier(int, Enum):
    """The floor on the load ladder. 1 = can never wait."""

    LIFE_HEALTH = 1  # life and health: vaccine chain, dialysis, drinking water
    BASIC = 2        # basic need: lighting, phone, food fridge, fan
    PRODUCTIVE = 3   # productive: ice maker, shop fridge, sewing, irrigation
    COMFORT = 4      # comfort: air conditioning, TV, extra freezer, leisure


TIER_ORDER: tuple[Tier, ...] = (
    Tier.LIFE_HEALTH,
    Tier.BASIC,
    Tier.PRODUCTIVE,
    Tier.COMFORT,
)


class ReasonCode(str, Enum):
    """Exactly one primary reason per decision. This is the explainability."""

    LIFELINE_FLOOR = "LIFELINE_FLOOR"
    CRITICALITY_ORDER = "CRITICALITY_ORDER"
    CREDIT_REDEMPTION = "CREDIT_REDEMPTION"
    PARTIAL_BUDGET = "PARTIAL_BUDGET"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    SUPPLY_UNAVAILABLE = "SUPPLY_UNAVAILABLE"
    VOLUNTARY_CURTAILMENT = "VOLUNTARY_CURTAILMENT"
    OVER_DECLARED = "OVER_DECLARED"
    DEFERRED_TO_STORAGE = "DEFERRED_TO_STORAGE"


State = Literal["granted", "partial", "deferred", "denied"]


@dataclass(frozen=True)
class Load:
    """A single load. The tier decides what happens if it is not served."""

    name: str
    tier: Tier
    energy_kwh: float  # requirement for this cycle
    shiftable: bool = False
    deadline_hour: float | None = None  # hour by which it can no longer be moved


@dataclass(frozen=True)
class Property:
    id: str
    category: Category
    occupants: int = 1
    vulnerability_flags: frozenset[str] = frozenset()
    loads: tuple[Load, ...] = ()
    #: Declared daily requirement. Used only to detect implausible declarations,
    #: never for the allocation itself.
    declared_kwh_per_day: float = 0.0
    historical_kwh_per_day: float = 0.0

    def loads_at(self, tier: Tier) -> tuple[Load, ...]:
        return tuple(l for l in self.loads if l.tier == tier)

    def declared_kwh(self) -> float:
        return sum(l.energy_kwh for l in self.loads)

    def declared_kwh_at(self, tiers: tuple[Tier, ...]) -> float:
        return sum(l.energy_kwh for l in self.loads if l.tier in tiers)

    @property
    def lifeline_kwh(self) -> float:
        """Minimum service level = tiers 1 and 2. By definition, not a separate
        number someone has to keep in sync."""
        return self.declared_kwh_at((Tier.LIFE_HEALTH, Tier.BASIC))

    @property
    def has_loads(self) -> bool:
        return bool(self.loads)


@dataclass(frozen=True)
class PropertyHistory:
    """Explicit state that is passed in and passed back out. Nothing is hidden
    inside the policy."""

    denied_streak: int = 0
    granted_kwh_total: float = 0.0
    curtailment_cycles: int = 0


@dataclass(frozen=True)
class AllocRequest:
    """Everything the component knows about the world in this cycle."""

    cycle_id: str
    hour_of_day: float  # 0.0 - 24.0. Replaces the clock, keeps the function pure.
    duration_s: int
    available_energy_kwh: float  # energy available to distribute this cycle
    available_power_kw: float
    properties: tuple[Property, ...]
    credits: Mapping[str, float] = field(default_factory=dict)
    history: Mapping[str, PropertyHistory] = field(default_factory=dict)
    curtailment_pledges: frozenset[str] = frozenset()
    storage_soc_kwh: float = 0.0
    #: Battery capacity. Needed to decide how much stored energy may go to
    #: comfort without threatening the critical load later at night.
    #: 0.0 = unknown, in which case the reserve rule is disabled.
    storage_capacity_kwh: float = 0.0
    is_islanded: bool = True
    grid_import_limit_kw: float = 0.0
    t_start: str = ""


@dataclass(frozen=True)
class Alloc:
    """Outcome for one property, with the reason spelled out."""

    property_id: str
    granted_energy_kwh: float
    granted_power_kw: float
    state: State
    reason_code: ReasonCode
    reason_text: str
    score_breakdown: Mapping[str, float] = field(default_factory=dict)
    granted_by_tier: Mapping[int, float] = field(default_factory=dict)


@dataclass(frozen=True)
class AllocResult:
    cycle_id: str
    alloc: Mapping[str, Alloc]
    credits_delta: Mapping[str, float]
    unserved_critical_kwh: float
    unserved_total_kwh: float
    history_out: Mapping[str, PropertyHistory]
    warnings: tuple[str, ...] = ()
    meta: Mapping[str, object] = field(default_factory=dict)

    def total_granted_kwh(self) -> float:
        return sum(a.granted_energy_kwh for a in self.alloc.values())


def is_finite(x: object) -> bool:
    """True if x is a finite number. Used to clean up garbage input."""
    try:
        f = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))  # NaN != NaN
