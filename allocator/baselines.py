"""Baselines to compare against. Without them there is no evidence for the
claim that the load ladder is better — only an opinion.

* FlatEqualPolicy      — "fair" means the same number of kWh per property. It
                         sounds reasonable, starves the clinic, and only cares
                         about how many properties there are, not about what the
                         energy is used for.
* FcfsPolicy           — first come, first served. What a prepaid meter
                         effectively does: whoever plugs in first gets it.
* NoTierFairnessPolicy — max-min fairness across all demand at once. Looks
                         mathematically fair, but treats a TV and a vaccine
                         fridge as equally important.
"""

from __future__ import annotations

import math
from dataclasses import replace

from .config import DEFAULT_CONFIG, Config
from .fairness import Demand, weighted_max_min_fair
from .models import (
    EPS,
    Alloc,
    AllocRequest,
    AllocResult,
    Property,
    PropertyHistory,
    ReasonCode,
    TIER_ORDER,
    Tier,
)


class _BasePolicy:
    name = "baseline"
    version = "1.0"
    supports_curtailment = True

    def allocate(
        self, req: AllocRequest, config: Config = DEFAULT_CONFIG
    ) -> AllocResult:
        raise NotImplementedError

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _spendable(req: AllocRequest, config: Config) -> float:
        energy = max(0.0, float(req.available_energy_kwh or 0.0))
        power = float(req.available_power_kw or 0.0)
        if req.duration_s > 0 and power > 0.0:
            energy = min(energy, power * req.duration_s / 3600.0)
        return energy * (1.0 - max(0.0, min(config.safety_margin, 0.5)))

    @staticmethod
    def _prepare(
        req: AllocRequest,
    ) -> tuple[tuple[Property, ...], dict[str, float]]:
        """Enforce voluntary curtailment: tiers 3 and 4 are removed for the
        properties that pledged to switch off. Every policy does the same, so
        the comparison is about allocation and not about behaviour."""
        pledged = frozenset(req.curtailment_pledges)
        props: list[Property] = []
        sacrifice: dict[str, float] = {}
        for p in sorted(req.properties, key=lambda x: x.id):
            if p.id in pledged:
                kept = tuple(
                    l for l in p.loads if l.tier not in (Tier.PRODUCTIVE, Tier.COMFORT)
                )
                sacrifice[p.id] = p.declared_kwh() - sum(l.energy_kwh for l in kept)
                props.append(replace(p, loads=kept))
            else:
                sacrifice[p.id] = 0.0
                props.append(p)
        return tuple(props), sacrifice

    def _finalise(
        self,
        req: AllocRequest,
        granted: dict[str, float],
        by_tier: dict[str, dict[int, float]],
        sacrifice: dict[str, float],
        spendable: float,
        warnings: list[str],
    ) -> AllocResult:
        alloc: dict[str, Alloc] = {}
        history_out: dict[str, PropertyHistory] = {}
        dt_h = (req.duration_s / 3600.0) if req.duration_s > 0 else 1.0

        for p in sorted(req.properties, key=lambda x: x.id):
            g = granted.get(p.id, 0.0)
            declared = p.declared_kwh()
            if declared <= EPS:
                state, reason, text = (
                    "granted",
                    ReasonCode.CRITICALITY_ORDER,
                    "no declared loads this cycle",
                )
            elif g >= declared - EPS:
                state, reason, text = (
                    "granted",
                    ReasonCode.CRITICALITY_ORDER,
                    "the whole declared requirement was met",
                )
            elif sacrifice.get(p.id, 0.0) > EPS:
                state, reason, text = (
                    "partial" if g > EPS else "deferred",
                    ReasonCode.VOLUNTARY_CURTAILMENT,
                    "curtailed comfort voluntarily",
                )
            elif g > EPS:
                state, reason, text = (
                    "partial",
                    ReasonCode.PARTIAL_BUDGET,
                    f"received {g:.3f} of {declared:.3f} kWh",
                )
            elif spendable <= EPS:
                state, reason, text = (
                    "denied",
                    ReasonCode.SUPPLY_UNAVAILABLE,
                    "no power available",
                )
            else:
                state, reason, text = (
                    "denied",
                    ReasonCode.BUDGET_EXHAUSTED,
                    "no energy left",
                )

            alloc[p.id] = Alloc(
                property_id=p.id,
                granted_energy_kwh=g,
                granted_power_kw=(g / dt_h) if dt_h > 0 else 0.0,
                state=state,
                reason_code=reason,
                reason_text=text,
                granted_by_tier=dict(by_tier.get(p.id, {})),
            )
            prev = req.history.get(p.id) or PropertyHistory()
            history_out[p.id] = PropertyHistory(
                denied_streak=prev.denied_streak + 1
                if (g <= EPS and declared > EPS)
                else 0,
                granted_kwh_total=prev.granted_kwh_total + g,
            )

        unserved_critical = math.fsum(
            max(
                0.0,
                p.declared_kwh_at((Tier.LIFE_HEALTH, Tier.BASIC))
                - by_tier.get(p.id, {}).get(int(Tier.LIFE_HEALTH), 0.0)
                - by_tier.get(p.id, {}).get(int(Tier.BASIC), 0.0),
            )
            for p in req.properties
        )
        unserved_total = math.fsum(
            max(
                0.0,
                p.declared_kwh() - granted.get(p.id, 0.0) - sacrifice.get(p.id, 0.0),
            )
            for p in req.properties
        )

        return AllocResult(
            cycle_id=req.cycle_id,
            alloc=alloc,
            credits_delta={p.id: 0.0 for p in req.properties},
            unserved_critical_kwh=unserved_critical,
            unserved_total_kwh=unserved_total,
            history_out=history_out,
            warnings=tuple(warnings),
            meta={
                "policy": f"{self.name}/{self.version}",
                "spendable_kwh": spendable,
                "granted_kwh": math.fsum(granted.values()),
                "scarcity": spendable + EPS
                < math.fsum(p.declared_kwh() for p in req.properties),
                "curtailed_kwh": math.fsum(sacrifice.values()),
            },
        )


class FlatEqualPolicy(_BasePolicy):
    """The same number of kWh per property, regardless of what it powers."""

    name = "baseline-flat-equal"

    def allocate(self, req, config=DEFAULT_CONFIG) -> AllocResult:
        spendable = self._spendable(req, config)
        props, sacrifice = self._prepare(req)
        granted: dict[str, float] = {}
        by_tier: dict[str, dict[int, float]] = {}
        if props:
            share = spendable / len(props)
            for p in props:
                granted[p.id] = min(share, p.declared_kwh())
                by_tier[p.id] = _spread_by_tier(p, granted[p.id])
        return self._finalise(req, granted, by_tier, sacrifice, spendable, [])


class FcfsPolicy(_BasePolicy):
    """First come, first served, in id order. At most 25 % per property."""

    name = "baseline-fcfs"

    def allocate(self, req, config=DEFAULT_CONFIG) -> AllocResult:
        spendable = self._spendable(req, config)
        props, sacrifice = self._prepare(req)
        granted: dict[str, float] = {}
        by_tier: dict[str, dict[int, float]] = {}
        remaining = spendable
        cap = spendable * 0.25 if spendable > 0 else 0.0
        for p in props:
            take = min(p.declared_kwh(), remaining, cap)
            granted[p.id] = take
            by_tier[p.id] = _spread_by_tier(p, take)
            remaining -= take
        return self._finalise(req, granted, by_tier, sacrifice, spendable, [])


class NoTierFairnessPolicy(_BasePolicy):
    """Max-min fairness across the whole requirement at once, no load ladder."""

    name = "baseline-no-tier-fairness"

    def allocate(self, req, config=DEFAULT_CONFIG) -> AllocResult:
        spendable = self._spendable(req, config)
        props, sacrifice = self._prepare(req)
        demands = [
            Demand(p.id, p.declared_kwh(), 1.0) for p in props if p.declared_kwh() > 0
        ]
        share = weighted_max_min_fair(demands, spendable)
        granted: dict[str, float] = {}
        by_tier: dict[str, dict[int, float]] = {}
        for p in props:
            g = share.get(p.id, 0.0)
            granted[p.id] = g
            by_tier[p.id] = _spread_by_tier(p, g)
        return self._finalise(req, granted, by_tier, sacrifice, spendable, [])


def _spread_by_tier(p: Property, total: float) -> dict[int, float]:
    """Spread a given amount across the property's loads in tier order. Used for
    reporting in the baselines only."""
    out: dict[int, float] = {}
    left = total
    for tier in TIER_ORDER:
        if left <= EPS:
            break
        need = sum(l.energy_kwh for l in p.loads if l.tier == tier)
        take = min(need, left)
        if take > 0:
            out[int(tier)] = take
        left -= take
    return out


BASELINES = {
    "flat-equal": FlatEqualPolicy,
    "fcfs": FcfsPolicy,
    "no-tier-fairness": NoTierFairnessPolicy,
}
