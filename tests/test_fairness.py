"""Unit tests for the fair division."""

from __future__ import annotations

import math

import pytest

from allocator.fairness import Demand, gini, weighted_max_min_fair


def test_empty_budget_returns_zero():
    out = weighted_max_min_fair([Demand("a", 5.0)], 0.0)
    assert out == {}


def test_negative_budget_returns_zero():
    assert weighted_max_min_fair([Demand("a", 5.0)], -3.0) == {}


def test_enough_to_cover_everything():
    out = weighted_max_min_fair([Demand("a", 1.0), Demand("b", 2.0)], 10.0)
    assert out == {"a": 1.0, "b": 2.0}


def test_sum_never_exceeds_budget():
    out = weighted_max_min_fair(
        [Demand("a", 5.0), Demand("b", 5.0), Demand("c", 5.0)], 7.0
    )
    assert math.fsum(out.values()) <= 7.0


def test_nobody_starves_if_the_budget_reaches_something():
    out = weighted_max_min_fair([Demand("a", 5.0), Demand("b", 5.0)], 2.0)
    assert out["a"] == pytest.approx(out["b"])
    assert out["a"] > 0


def test_small_demand_is_capped_and_the_rest_is_shared():
    # a only needs 0.1. The remaining budget must go to b, not be wasted.
    out = weighted_max_min_fair([Demand("a", 0.1), Demand("b", 10.0)], 5.0)
    assert out["a"] == pytest.approx(0.1)
    assert out["b"] == pytest.approx(4.9, abs=1e-6)


def test_higher_weight_receives_more():
    out = weighted_max_min_fair(
        [Demand("weak", 10.0, 1.0), Demand("strong", 10.0, 3.0)], 8.0
    )
    assert out["strong"] > out["weak"]
    assert out["strong"] == pytest.approx(3 * out["weak"], rel=1e-6)


def test_deterministic_at_equal_scores():
    demands = [Demand("b", 2.0), Demand("a", 2.0), Demand("c", 2.0)]
    first = weighted_max_min_fair(demands, 3.0)
    for _ in range(50):
        assert weighted_max_min_fair(list(reversed(demands)), 3.0) == first


def test_zero_requirement_is_ignored():
    out = weighted_max_min_fair([Demand("a", 0.0), Demand("b", 1.0)], 1.0)
    assert "a" not in out
    assert out["b"] == pytest.approx(1.0)


def test_gini_equal_is_zero():
    assert gini([1.0, 1.0, 1.0, 1.0]) == pytest.approx(0.0, abs=1e-9)


def test_gini_skewed_is_high():
    assert gini([0.0, 0.0, 0.0, 10.0]) > 0.7


def test_gini_empty_is_zero():
    assert gini([]) == 0.0
