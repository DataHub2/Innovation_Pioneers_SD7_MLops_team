"""Shared helpers for the tests."""

from __future__ import annotations

import math

from allocator.config import DEFAULT_CONFIG, Config
from allocator.models import (
    EPS,
    AllocRequest,
    AllocResult,
    Category,
    Load,
    Property,
    Tier,
)

LoadSpecTuple = tuple[str, Tier, float]


def make_property(
    pid: str,
    loads: tuple[LoadSpecTuple, ...],
    category: Category = Category.HOUSEHOLD,
    occupants: int = 3,
    flags: frozenset[str] = frozenset(),
    declared_kwh_per_day: float = 0.0,
    historical_kwh_per_day: float = 0.0,
) -> Property:
    return Property(
        id=pid,
        category=category,
        occupants=occupants,
        vulnerability_flags=flags,
        loads=tuple(Load(n, t, e) for n, t, e in loads),
        declared_kwh_per_day=declared_kwh_per_day,
        historical_kwh_per_day=historical_kwh_per_day,
    )


def make_request(
    properties: tuple[Property, ...],
    energy_kwh: float,
    hour: float = 19.0,
    power_kw: float = 0.0,
    duration_s: int = 900,
    credits: dict[str, float] | None = None,
    history: dict | None = None,
    pledges: frozenset[str] = frozenset(),
    storage_soc_kwh: float = 0.0,
    storage_capacity_kwh: float = 0.0,
) -> AllocRequest:
    return AllocRequest(
        cycle_id="test",
        hour_of_day=hour,
        duration_s=duration_s,
        available_energy_kwh=energy_kwh,
        available_power_kw=power_kw,
        properties=properties,
        credits=credits or {},
        history=history or {},
        curtailment_pledges=pledges,
        storage_soc_kwh=storage_soc_kwh,
        storage_capacity_kwh=storage_capacity_kwh,
    )


class CheckingPolicy:
    """Wraps a policy and checks invariants I1, I2, I6, I7 and I10 on every
    single call. Used by the simulation-based tests."""

    def __init__(self, inner, config: Config = DEFAULT_CONFIG) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", type(inner).__name__)
        self.config = config
        self.calls = 0

    def allocate(self, req: AllocRequest, config: Config | None = None) -> AllocResult:
        res = self.inner.allocate(req, self.config)
        self.calls += 1
        check_invariants(req, res, self.config)
        return res


def check_invariants(
    req: AllocRequest, res: AllocResult, config: Config = DEFAULT_CONFIG
) -> None:
    budget = max(0.0, req.available_energy_kwh) * (1.0 - config.safety_margin)
    budget = max(0.0, budget)
    if req.duration_s > 0 and req.available_power_kw > 0:
        budget = min(budget, req.available_power_kw * req.duration_s / 3600.0)

    granted_total = math.fsum(a.granted_energy_kwh for a in res.alloc.values())

    # I1: never more than the budget
    assert granted_total <= budget + 1e-9, f"I1 broken: {granted_total} > {budget}"

    # I2: never more power than available
    power_total = math.fsum(a.granted_power_kw for a in res.alloc.values())
    if req.available_power_kw > 0:
        assert power_total <= req.available_power_kw + 1e-6, (
            f"I2 broken: {power_total} > {req.available_power_kw}"
        )

    by_id = {p.id: p for p in req.properties}
    for a in res.alloc.values():
        p = by_id.get(a.property_id)
        assert p is not None, f"I6: unknown property {a.property_id} in the result"
        g = a.granted_energy_kwh
        # I10: no NaN, no negative numbers
        assert math.isfinite(g) and g >= -EPS, f"I10 broken for {a.property_id}: {g}"
        assert a.reason_code is not None, "I6: decision without a reason"
        # I7: nobody receives more than they declared
        assert g <= p.declared_kwh() + 1e-9, (
            f"I7 broken for {a.property_id}: {g} > {p.declared_kwh()}"
        )

    # I4: credits cannot go negative from the delta alone
    for pid, delta in res.credits_delta.items():
        assert math.isfinite(delta), f"I4/I10: credit delta is not a number for {pid}"


def spendable(req: AllocRequest, config: Config = DEFAULT_CONFIG) -> float:
    budget = max(0.0, req.available_energy_kwh) * (1.0 - config.safety_margin)
    if req.duration_s > 0 and req.available_power_kw > 0:
        budget = min(budget, req.available_power_kw * req.duration_s / 3600.0)
    return budget
