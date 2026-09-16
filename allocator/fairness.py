"""Fair division inside a tier.

The core is *weighted max-min fairness* (progressive water filling):

* Everyone competing grows in proportion to their weight.
* Whoever needs little is satisfied early and "capped", then the remainder is
  shared among the rest.
* Nobody receives more than they need, and nobody receives zero as long as the
  budget can reach them.

That property is what stops one household from starving another *within the
same tier*, and it is deterministic: at exactly equal weight and equal need, the
key (property id) decides, never Python's dict ordering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

#: Numerical safety margin. Ensures the sum can never exceed the budget because
#: of floating point error.
NUMERIC_MARGIN = 1e-9


@dataclass(frozen=True)
class Demand:
    key: str
    requirement_kwh: float
    weight: float = 1.0


def weighted_max_min_fair(demands: Iterable[Demand], budget: float) -> dict[str, float]:
    """Distribute `budget` kWh across `demands`.

    Returns key -> allocated kWh. The sum is always <= budget.
    """

    try:
        budget_f = float(budget)
    except (TypeError, ValueError):
        budget_f = 0.0
    if not math.isfinite(budget_f) or budget_f <= 0.0:
        return {}

    items = [
        d
        for d in demands
        if math.isfinite(d.requirement_kwh) and d.requirement_kwh > 0.0
    ]
    if not items:
        return {}

    # Deterministic order: ascending requirement per weight, then by key.
    items.sort(key=lambda d: (d.requirement_kwh / max(d.weight, 0.0), d.key))

    n = len(items)

    # Suffix sums of the weights. Without them the loop below is O(n^2), which
    # shows up immediately at 500 properties.
    suffix_weight = [0.0] * (n + 1)
    for idx in range(n - 1, -1, -1):
        suffix_weight[idx] = suffix_weight[idx + 1] + items[idx].weight

    alloc: dict[str, float] = {}
    remaining = budget_f * (1.0 - NUMERIC_MARGIN)
    prev_level = 0.0
    i = 0

    while i < n:
        weight_sum = suffix_weight[i]
        lvl = items[i].requirement_kwh / max(items[i].weight, 0.0)
        cost = (lvl - prev_level) * weight_sum
        if cost <= remaining:
            remaining -= cost
            prev_level = lvl
            i += 1
            continue
        level = prev_level + (remaining / weight_sum if weight_sum > 0 else 0.0)
        for idx in range(i, n):
            alloc[items[idx].key] = level * items[idx].weight
        remaining = 0.0
        break

    for idx in range(i):
        alloc[items[idx].key] = items[idx].requirement_kwh

    return alloc


def total(alloc: Mapping[str, float]) -> float:
    return math.fsum(alloc.values())


def gini(values: Sequence[float]) -> float:
    """Gini coefficient. 0 = perfectly equal, 1 = everything to one."""
    xs = sorted(float(v) for v in values)
    n = len(xs)
    if n == 0:
        return 0.0
    s = math.fsum(xs)
    if s <= 0.0:
        return 0.0
    cumulative = math.fsum((idx + 1) * x for idx, x in enumerate(xs))
    return (2.0 * cumulative) / (n * s) - (n + 1.0) / n
