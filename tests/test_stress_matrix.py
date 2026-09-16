"""The stress matrix S1-S13 (docs/ALLOCATION_CONTRACT.md section 8).

Each test provokes a specific failure. The point is to be able to say "we went
looking for ways to break it and found none" — not "it seems to work".
"""

from __future__ import annotations

import math
import time

import pytest

from allocator.config import Config
from allocator.models import Category, ReasonCode, Tier
from allocator.policy import TieredNeedPolicy
from harness.scenario import build_barangay
from harness.simulate import SimConfig, Simulator

from .helpers import check_invariants, make_property, make_request

POLICY = TieredNeedPolicy()


# --------------------------------------------------------- S1 zero supply
def test_s1_zero_supply_does_not_crash():
    world = (
        make_property("clinic", (("vaccine_chain", Tier.LIFE_HEALTH, 0.5),),
                      category=Category.CLINIC, flags=frozenset({"cold_chain"})),
        make_property("household", (("light", Tier.BASIC, 0.5),)),
    )
    req = make_request(world, energy_kwh=0.0)
    res = POLICY.allocate(req)
    check_invariants(req, res)
    assert all(a.granted_energy_kwh == 0.0 for a in res.alloc.values())
    assert res.alloc["household"].reason_code is ReasonCode.SUPPLY_UNAVAILABLE


def test_s1_empty_property_list_does_not_crash():
    req = make_request((), energy_kwh=5.0)
    res = POLICY.allocate(req)
    assert res.alloc == {}
    assert res.unserved_critical_kwh == 0.0


def test_s1_negative_supply_becomes_zero():
    world = (make_property("h", (("light", Tier.BASIC, 0.5),)),)
    req = make_request(world, energy_kwh=-5.0)
    res = POLICY.allocate(req)
    check_invariants(req, res)


# --------------------------------------------------- S2 demand three times supply
def test_s2_oversubscription_keeps_the_budget_and_the_lifeline():
    world = tuple(
        make_property(f"hh{i}", (("light", Tier.BASIC, 0.3), ("tv", Tier.COMFORT, 1.0)))
        for i in range(10)
    )
    demand = sum(p.declared_kwh() for p in world)
    req = make_request(world, energy_kwh=demand / 3.0)
    res = POLICY.allocate(req)
    check_invariants(req, res)
    # The full requirement cannot be met, but everyone must receive something
    # on their tier.
    assert all(a.granted_energy_kwh > 0 for a in res.alloc.values())


# ------------------------------------------------- S3 properties join and leave
def test_s3_properties_joining_mid_run_raise_no_exception():
    specs = build_barangay(n_households=6, seed=11)
    sim = Simulator(specs, sim_config=SimConfig(cycles_per_day=48, days=1, kwp=6.0))
    result = sim.run(POLICY)
    assert result.steps == 48
    assert not any("Traceback" in w for w in result.warnings)


# ------------------------------------------------------------- S4 free rider
def test_s4_implausible_declaration_is_scaled_down():
    world = (
        make_property(
            "greedy",
            (("light", Tier.BASIC, 20.0),),
            declared_kwh_per_day=200.0,
            historical_kwh_per_day=10.0,
        ),
        make_property(
            "normal",
            (("light", Tier.BASIC, 0.2),),
            declared_kwh_per_day=2.0,
            historical_kwh_per_day=2.0,
        ),
    )
    req = make_request(world, energy_kwh=20.0)
    res = POLICY.allocate(req)
    assert any("declares" in w for w in res.warnings)
    # The greedy property cannot take the whole budget despite its declaration.
    assert res.alloc["greedy"].granted_energy_kwh <= 20.0 * 3.0 / (10.0 / 20.0) + 1e-6
    assert res.alloc["normal"].granted_energy_kwh == pytest.approx(0.2, abs=1e-6)


def test_s4_without_history_nothing_can_be_scaled_down():
    world = (make_property("new", (("light", Tier.BASIC, 1.0),)),)
    res = POLICY.allocate(make_request(world, energy_kwh=1.0))
    assert res.warnings == ()
    # The safety margin holds back 2 %, so an exact requirement is never reached.
    assert res.alloc["new"].granted_energy_kwh == pytest.approx(0.98, abs=1e-6)


# -------------------------------------------------------------- S5 tie storm
def test_s5_equal_scores_give_an_identical_result():
    world = tuple(
        make_property(f"h{i:02d}", (("light", Tier.BASIC, 0.5),)) for i in range(60)
    )
    req = make_request(world, energy_kwh=12.0)
    first = POLICY.allocate(req)
    for _ in range(100):
        assert POLICY.allocate(req) == first


# ------------------------------------------------------------ S6 garbage config
def test_s6_negative_weight_does_not_crash():
    config = Config(vulnerability_bonus={"dialysis": -5.0})
    world = (
        make_property("h", (("light", Tier.BASIC, 1.0),), flags=frozenset({"dialysis"})),
    )
    req = make_request(world, energy_kwh=1.0)
    res = POLICY.allocate(req, config)
    check_invariants(req, res, config)
    assert res.alloc["h"].granted_energy_kwh > 0


def test_s6_zero_and_invalid_safety_margin():
    world = (make_property("h", (("light", Tier.BASIC, 1.0),)),)
    for margin in (0.0, -1.0, 2.0):
        config = Config(safety_margin=margin)
        req = make_request(world, energy_kwh=1.0)
        res = POLICY.allocate(req, config)
        assert res.total_granted_kwh() >= 0.0


def test_s6_missing_vulnerability_flag_gives_no_bonus():
    config = Config(vulnerability_bonus={})
    world = (
        make_property("h", (("light", Tier.BASIC, 1.0),), flags=frozenset({"unknown"})),
    )
    res = POLICY.allocate(make_request(world, energy_kwh=1.0), config)
    assert res.alloc["h"].score_breakdown["weight_t2"] == pytest.approx(1.0)


# ------------------------------------------- S7 empty battery at the evening peak
def test_s7_empty_battery_protects_the_clinic_and_punishes_comfort():
    world = (
        make_property(
            "clinic",
            (("vaccine_chain", Tier.LIFE_HEALTH, 0.4), ("lounge_ac", Tier.COMFORT, 2.0)),
            category=Category.CLINIC,
            flags=frozenset({"cold_chain"}),
        ),
        make_property("household", (("light", Tier.BASIC, 0.3), ("aircon", Tier.COMFORT, 3.0))),
        make_property("house_with_ac_only", (("aircon", Tier.COMFORT, 1.0),)),
    )
    req = make_request(
        world, energy_kwh=0.5, hour=19.0, storage_soc_kwh=5.0, storage_capacity_kwh=60.0
    )
    res = POLICY.allocate(req)
    # The clinic's critical load comes before everything else.
    assert res.alloc["clinic"].granted_by_tier.get(1, 0.0) == pytest.approx(0.4, abs=1e-6)
    # No comfort at all while the battery is below the reserve level.
    assert res.alloc["household"].granted_by_tier.get(4, 0.0) == 0.0
    assert res.alloc["house_with_ac_only"].granted_energy_kwh == 0.0
    assert res.alloc["house_with_ac_only"].reason_code is ReasonCode.DEFERRED_TO_STORAGE


def test_s7_reserve_rule_is_disabled_without_capacity():
    """Without a battery capacity the reserve cannot be computed, so it does not
    apply. That is a deliberate choice, not a silent failure."""
    world = (make_property("h", (("aircon", Tier.COMFORT, 3.0),)),)
    req = make_request(world, energy_kwh=3.0, storage_soc_kwh=1.0, storage_capacity_kwh=0.0)
    res = POLICY.allocate(req)
    assert res.alloc["h"].granted_energy_kwh == pytest.approx(2.94, abs=1e-6)


# ------------------------------------------------------ S8 four cloudy days
def test_s8_four_cloudy_days_prioritise_critical_load_over_comfort():
    """The comparison is what matters: same bad weather, same village, only a
    different allocation."""
    from allocator.baselines import FlatEqualPolicy, NoTierFairnessPolicy

    specs = build_barangay(n_households=10, seed=5)
    cfg = SimConfig(
        cycles_per_day=96, days=4, kwp=12.0, battery_kwh=40.0,
        cloud_by_day=(0.35, 0.3, 0.25, 0.4),
    )
    ours = Simulator(specs, sim_config=cfg).run(POLICY)
    flat = Simulator(specs, sim_config=cfg).run(FlatEqualPolicy())
    naive = Simulator(specs, sim_config=cfg).run(NoTierFairnessPolicy())

    assert ours.tier1_uptime > flat.tier1_uptime
    assert ours.tier1_uptime > naive.tier1_uptime
    assert ours.unserved_critical_kwh < flat.unserved_critical_kwh
    assert ours.unserved_critical_kwh < naive.unserved_critical_kwh
    # And the price is paid by comfort, not by the critical load.
    assert ours.comfort_service < flat.comfort_service


# --------------------------------------------------- S9 midnight and day bounds
def test_s9_midnight_and_day_boundaries():
    world = (make_property("h", (("light", Tier.BASIC, 0.5),)),)
    for hour in (0.0, 0.25, 12.0, 23.75, 24.0):
        req = make_request(world, energy_kwh=1.0, hour=hour)
        res = POLICY.allocate(req)
        check_invariants(req, res)


def test_s9_invalid_duration_does_not_divide_by_zero():
    world = (make_property("h", (("light", Tier.BASIC, 0.5),)),)
    req = make_request(world, energy_kwh=1.0, duration_s=0)
    res = POLICY.allocate(req)
    assert math.isfinite(res.total_granted_kwh())


# ------------------------------------------------------------- S10 long drift
def test_s10_thirty_days_without_accounting_drift():
    specs = build_barangay(n_households=6, seed=9)
    cfg = SimConfig(cycles_per_day=48, days=30, kwp=8.0, battery_kwh=30.0,
                    cloud_by_day=(0.8, 0.9, 0.6, 0.7))
    result = Simulator(specs, sim_config=cfg).run(POLICY)
    assert result.steps == 48 * 30
    assert all(math.isfinite(v) and v >= 0.0 for v in result.credits_end.values())
    assert max(result.credits_end.values()) < 1e4  # no inflated currency
    assert math.isfinite(result.delivered_kwh) and result.delivered_kwh > 0


# --------------------------------------------------------------- S11 performance
def _big_world(n: int):
    return tuple(
        make_property(
            f"p{i:04d}",
            (
                ("light", Tier.BASIC, 0.3),
                ("fridge", Tier.BASIC, 0.2),
                ("aircon", Tier.COMFORT, 1.5),
                ("pump", Tier.PRODUCTIVE, 0.4),
            ),
        )
        for i in range(n)
    )


@pytest.mark.parametrize("n,budget_ms", [(60, 50.0), (500, 200.0)])
def test_s11_performance(n, budget_ms):
    world = _big_world(n)
    req = make_request(world, energy_kwh=n * 1.0)
    POLICY.allocate(req)  # warm up
    times = []
    for _ in range(30):
        t0 = time.perf_counter()
        POLICY.allocate(req)
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    p99 = times[int(0.99 * (len(times) - 1))]
    assert p99 < budget_ms, f"p99 {p99:.1f} ms > {budget_ms} ms for {n} properties"


# --------------------------------------------------------------- S12 broken data
def test_s12_duplicate_id_is_ignored_with_a_warning():
    world = (
        make_property("duplicate", (("light", Tier.BASIC, 1.0),)),
        make_property("duplicate", (("light", Tier.BASIC, 5.0),)),
    )
    res = POLICY.allocate(make_request(world, energy_kwh=10.0))
    assert any("duplicate" in w for w in res.warnings)
    assert res.alloc["duplicate"].granted_energy_kwh == pytest.approx(1.0, abs=1e-6)


def test_s12_nan_in_a_load_is_skipped():
    world = (
        make_property("h", (("light", Tier.BASIC, float("nan")), ("tv", Tier.COMFORT, 0.5))),
    )
    res = POLICY.allocate(make_request(world, energy_kwh=1.0))
    assert any("invalid energy" in w for w in res.warnings)
    assert math.isfinite(res.alloc["h"].granted_energy_kwh)


def test_s12_property_with_no_loads_receives_nothing():
    world = (make_property("empty", ()),)
    res = POLICY.allocate(make_request(world, energy_kwh=1.0))
    assert res.alloc["empty"].granted_energy_kwh == 0.0


# ------------------------------------------------------- S13 floating point edges
@pytest.mark.parametrize("energy", [1e-12, 0.1, 0.1 + 1e-15, 3.3333333333333335])
def test_s13_rounding_never_exceeds_the_budget(energy):
    world = tuple(
        make_property(f"h{i}", (("light", Tier.BASIC, 0.3333333333333333),))
        for i in range(7)
    )
    req = make_request(world, energy_kwh=energy)
    res = POLICY.allocate(req)
    check_invariants(req, res)


def test_s13_sum_stays_within_budget_over_many_repeats():
    world = tuple(
        make_property(f"h{i}", (("light", Tier.BASIC, 0.7),)) for i in range(9)
    )
    for _ in range(200):
        req = make_request(world, energy_kwh=2.0)
        res = POLICY.allocate(req)
        assert res.total_granted_kwh() <= 2.0 * (1.0 - Config().safety_margin)
