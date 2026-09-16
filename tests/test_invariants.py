"""Invariants I1-I10 (docs/ALLOCATION_CONTRACT.md section 6).

Each test corresponds to one invariant. This is the proof that the algorithm
cannot do certain things — not an opinion that it looks reasonable.
"""

from __future__ import annotations

import math

import pytest

from allocator.config import DEFAULT_CONFIG, Config
from allocator.models import Category, ReasonCode, Tier
from allocator.policy import TieredNeedPolicy
from harness.scenario import build_barangay
from harness.simulate import SimConfig, Simulator

from .helpers import CheckingPolicy, check_invariants, make_property, make_request

POLICY = TieredNeedPolicy()


def _small_world():
    return (
        make_property(
            "clinic",
            (("vaccine_chain", Tier.LIFE_HEALTH, 0.5), ("lounge_ac", Tier.COMFORT, 1.0)),
            category=Category.CLINIC,
            flags=frozenset({"cold_chain"}),
        ),
        make_property("household_a", (("light", Tier.BASIC, 0.3), ("tv", Tier.COMFORT, 0.5))),
        make_property(
            "household_b",
            (("light", Tier.BASIC, 0.4), ("aircon", Tier.COMFORT, 2.0)),
            occupants=6,
        ),
    )


# ---------------------------------------------------------------- I1 and I2
def test_i1_never_more_than_the_budget():
    for energy in (0.0, 0.01, 0.4, 1.0, 5.0, 100.0):
        req = make_request(_small_world(), energy)
        res = POLICY.allocate(req)
        check_invariants(req, res)


def test_i2_power_limit_holds():
    req = make_request(_small_world(), energy_kwh=10.0, power_kw=1.0, duration_s=900)
    res = POLICY.allocate(req)
    total_power = math.fsum(a.granted_power_kw for a in res.alloc.values())
    assert total_power <= 1.0 + 1e-6
    check_invariants(req, res)


# ---------------------------------------------------------------------- I3
def test_i3_lifeline_comes_before_everything_when_possible():
    world = _small_world()
    lifeline = sum(p.lifeline_kwh for p in world)
    req = make_request(world, energy_kwh=lifeline / 0.98)  # just above the lifeline
    res = POLICY.allocate(req)
    for p in world:
        granted_lifeline = sum(
            v for k, v in res.alloc[p.id].granted_by_tier.items() if k in (1, 2)
        )
        assert granted_lifeline == pytest.approx(p.lifeline_kwh, abs=1e-6), p.id


def test_i3_comfort_gets_nothing_before_anyone_lacks_lifeline():
    world = _small_world()
    req = make_request(world, energy_kwh=0.7)
    res = POLICY.allocate(req)
    comfort = sum(
        v for a in res.alloc.values() for k, v in a.granted_by_tier.items() if k == 4
    )
    assert comfort == 0.0


# ---------------------------------------------------------------------- I5
def test_i5_deterministic():
    req = make_request(_small_world(), energy_kwh=1.2345)
    first = POLICY.allocate(req)
    for _ in range(20):
        assert POLICY.allocate(req) == first


def test_i5_deterministic_at_exactly_equal_scores():
    world = tuple(
        make_property(f"h{i}", (("light", Tier.BASIC, 0.5),)) for i in range(12)
    )
    req = make_request(world, energy_kwh=1.5)
    first = POLICY.allocate(req)
    for _ in range(20):
        assert POLICY.allocate(req) == first
    # At exactly equal scores the key decides — not dict ordering.
    assert first.alloc["h0"].granted_energy_kwh == pytest.approx(
        first.alloc["h11"].granted_energy_kwh, rel=1e-6
    )


# ---------------------------------------------------------------------- I6
def test_i6_every_property_gets_exactly_one_decision():
    world = _small_world()
    res = POLICY.allocate(make_request(world, energy_kwh=1.0))
    assert set(res.alloc) == {p.id for p in world}
    for a in res.alloc.values():
        assert isinstance(a.reason_code, ReasonCode)


# ---------------------------------------------------------------------- I7
def test_i7_nobody_receives_more_than_declared():
    world = _small_world()
    res = POLICY.allocate(make_request(world, energy_kwh=1000.0))
    for p in world:
        assert res.alloc[p.id].granted_energy_kwh <= p.declared_kwh() + 1e-9


# ---------------------------------------------------------------------- I8
def test_i8_starvation_warning_after_sustained_shortage():
    """A property denied many cycles in a row must be flagged, not silenced."""
    config = Config(starvation_cycles=3)
    world = (make_property("h", (("light", Tier.BASIC, 0.5),)),)
    history = {}
    seen_warning = False
    for _ in range(5):
        res = POLICY.allocate(
            make_request(world, energy_kwh=0.0, history=history), config
        )
        history = dict(res.history_out)
        seen_warning = seen_warning or any("starvation warning" in w for w in res.warnings)
    assert seen_warning


def test_i8_warning_does_not_claim_surplus_that_did_not_exist():
    config = Config(starvation_cycles=2)
    world = (make_property("h", (("light", Tier.BASIC, 0.5),)),)
    history = {}
    for _ in range(3):
        res = POLICY.allocate(
            make_request(world, energy_kwh=0.0, history=history), config
        )
        history = dict(res.history_out)
    assert all("while surplus" not in w for w in res.warnings)


def test_i8_nobody_starves_while_the_budget_is_above_zero():
    """The stronger guarantee: because allocation is max-min fair, nobody with a
    requirement receives zero as long as energy remains."""
    world = tuple(
        make_property(f"h{i}", (("light", Tier.BASIC, float(10 + i)),))
        for i in range(20)
    )
    for energy in (0.01, 0.5, 3.0, 20.0, 137.0):
        res = POLICY.allocate(make_request(world, energy_kwh=energy))
        assert all(a.granted_energy_kwh > 0 for a in res.alloc.values()), energy


def test_i8_history_accumulates_correctly():
    world = (make_property("h", (("light", Tier.BASIC, 1.0),)),)
    req = make_request(world, energy_kwh=0.0)
    res = POLICY.allocate(req)
    assert res.history_out["h"].denied_streak == 1
    req2 = make_request(world, energy_kwh=0.0, history=dict(res.history_out))
    assert POLICY.allocate(req2).history_out["h"].denied_streak == 2


# ----------------------------------------------------------------- I4 / I9
def test_i9_credit_accounting_is_consistent():
    world = (
        make_property("h1", (("light", Tier.BASIC, 0.5), ("tv", Tier.COMFORT, 1.0))),
        make_property("h2", (("light", Tier.BASIC, 0.5),)),
    )
    req = make_request(world, energy_kwh=1.0, pledges=frozenset({"h1"}))
    res = POLICY.allocate(req)
    # Only h1 can have earned credits, and only for comfort it gave up.
    assert res.credits_delta["h2"] == 0.0
    assert res.credits_delta["h1"] == pytest.approx(
        1.0 * DEFAULT_CONFIG.credit_earn_per_kwh
    )


def test_i4_no_credits_without_scarcity():
    world = (
        make_property("h1", (("light", Tier.BASIC, 0.5), ("tv", Tier.COMFORT, 1.0))),
    )
    req = make_request(world, energy_kwh=100.0, pledges=frozenset({"h1"}))
    res = POLICY.allocate(req)
    assert res.credits_delta["h1"] == 0.0  # no scarcity means nothing to farm


def test_i4_decay_can_never_make_a_balance_negative():
    world = (make_property("h1", (("light", Tier.BASIC, 0.5),)),)
    credits = {"h1": 10.0}
    balance = credits["h1"]
    for _ in range(96):
        req = make_request(world, energy_kwh=1.0, credits=credits, duration_s=900)
        res = POLICY.allocate(req)
        balance = balance + res.credits_delta["h1"]
        credits = {"h1": balance}
        assert balance >= 0.0
    assert balance < 10.0  # decay is doing something


# --------------------------------------------------------------------- I10
def test_i10_no_nan_and_no_negative_numbers():
    req = make_request(_small_world(), energy_kwh=float("nan"))
    res = POLICY.allocate(req)
    check_invariants(req, res)
    for a in res.alloc.values():
        assert a.granted_energy_kwh == 0.0


def test_i10_infinite_supply_does_not_yield_infinite_allocation():
    world = _small_world()
    req = make_request(world, energy_kwh=float("inf"))
    res = POLICY.allocate(req)
    for p in world:
        assert res.alloc[p.id].granted_energy_kwh <= p.declared_kwh() + 1e-9


# ------------------------------------------- invariants across a whole run
def test_invariants_hold_across_a_full_simulation():
    specs = build_barangay(n_households=8, seed=3)
    cfg = SimConfig(cycles_per_day=96, days=2, kwp=8.0, battery_kwh=30.0)
    sim = Simulator(specs, sim_config=cfg)
    checked = CheckingPolicy(TieredNeedPolicy())
    result = sim.run(checked)  # type: ignore[arg-type]
    assert checked.calls == 96 * 2
    assert result.delivered_kwh > 0
