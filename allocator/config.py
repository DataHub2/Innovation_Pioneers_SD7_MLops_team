"""Configuration. This is the policy — not the code.

Every number that expresses a value judgement lives here, never hard-coded in
the algorithm. That is what lets a village change its own priorities without a
developer touching the code, and it is what keeps the algorithm free of an
opinion of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping


@dataclass(frozen=True)
class Config:
    #: Share of available energy held back. Protects against metering error and
    #: ensures rounding can never break the budget.
    safety_margin: float = 0.02

    #: Vulnerability bonus per flag. Applies to tiers 1 and 2 ONLY — that is,
    #: to need, not to comfort. A dialysis machine always outweighs a TV.
    vulnerability_bonus: Mapping[str, float] = field(
        default_factory=lambda: {
            "dialysis": 2.0,
            "cold_chain": 1.5,
            "medical_device": 1.5,
            "elderly": 1.3,
            "pwd": 1.3,
            "infant": 1.2,
        }
    )

    #: Credits are a bounded reciprocity term, not a currency. A property that
    #: curtails voluntarily gains a *limited* advantage within its own tier.
    #: The cap is what makes it impossible to buy your way past a critical load.
    credit_weight_per_unit: float = 0.02
    credit_weight_cap: float = 0.5        # at most +50 % within the same tier
    credit_earn_per_kwh: float = 1.0      # earned per kWh of comfort given up
    credit_decay_per_day: float = 0.05    # prevents inherited dominance

    #: Reserve rule: how full the battery must be before a tier may draw on
    #: stored energy. Without it, comfort drinks the battery during the day and
    #: the village is dark when the critical load is needed at night.
    storage_reserve_productive: float = 0.25
    storage_reserve_comfort: float = 0.50

    #: Declaration check. A household cannot declare an arbitrary amount.
    declaration_ratio_cap: float = 3.0
    cycles_per_day: int = 96

    #: When a property is denied too many cycles in a row.
    starvation_cycles: int = 6

    tie_break: str = "property_id_asc"

    def with_overrides(self, **kwargs: Any) -> "Config":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        out = dict(self.__dict__)
        out["vulnerability_bonus"] = dict(self.vulnerability_bonus)
        return out


DEFAULT_CONFIG = Config()
