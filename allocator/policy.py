"""TieredNeedPolicy — the algorithm itself.

In prose:

    1. Fill the load ladder from the bottom up. Tier 1 first, then 2, 3, 4.
    2. On each tier: non-shiftable loads first, shiftable loads from surplus.
    3. Within each group: weighted max-min fairness. Nobody receives zero while
       someone else on the same tier receives more than they need.

Nowhere does one property get compared against another property as a whole.
There are only loads and tiers. That is why a household can never take energy
from a vaccine cold chain — they sit on different tiers and never compete.

Semantics worth knowing:
* `available_power_kw <= 0` is read as "no power limit supplied". If a power
  limit is supplied, it caps the budget via duration_s, which upholds I2.
* A shiftable load past its deadline is treated as non-shiftable, so a water
  tank is genuinely full by evening.
* Curtailed comfort (a pledge) is removed from the demand and earns credits.
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
    Load,
    Property,
    PropertyHistory,
    ReasonCode,
    State,
    TIER_ORDER,
    Tier,
    is_finite,
)

#: Tiers that may be curtailed voluntarily. Life and basic need can never be
#: traded for credits — that is the whole point of the cap in the credit term.
_CURTAILABLE_TIERS = (Tier.PRODUCTIVE, Tier.COMFORT)

#: Relative tolerance for requirement comparisons.
_REL_TOL = 1e-6

#: Tolerance for calling a requirement "covered". A deviation below 0.5 % is a
#: rounding artefact of the division, not rationing, and should not make a UI
#: show "partial" next to the text "received 100 % of its need". The exact
#: numbers remain in `granted_energy_kwh`; this only affects the verdict.
_FULL_TOL = 5e-3


class TieredNeedPolicy:
    """Need-based allocation through a load ladder. Deterministic, stateless."""

    name = "tiered-need"
    version = "1.0"

    # ------------------------------------------------------------------- API
    def allocate(
        self, req: AllocRequest, config: Config = DEFAULT_CONFIG
    ) -> AllocResult:
        warnings: list[str] = []

        spendable = self._spendable(req, config)
        properties, capped_ids = self._normalise(req, config, warnings)

        credits = {
            p.id: max(0.0, _safe_float(req.credits.get(p.id, 0.0)))
            for p in properties
        }
        pledged = frozenset(req.curtailment_pledges)

        declared_total = math.fsum(p.declared_kwh() for p in properties)
        scarcity = spendable + EPS < declared_total

        granted: dict[str, float] = {p.id: 0.0 for p in properties}
        by_tier: dict[str, dict[int, float]] = {p.id: {} for p in properties}
        sacrifice: dict[str, float] = {p.id: 0.0 for p in properties}

        remaining = spendable

        # The reserve rule: productive and comfort may not draw on the part of
        # the battery that the critical load needs later.
        blocked_tiers = frozenset(
            tier
            for tier, fraction in (
                (Tier.PRODUCTIVE, config.storage_reserve_productive),
                (Tier.COMFORT, config.storage_reserve_comfort),
            )
            if self._storage_blocked(req, fraction)
        )

        # ---- The ladder: tier by tier, non-shiftable before shiftable.
        for tier in TIER_ORDER:
            blocked = tier in blocked_tiers
            for flexible_pass in (False, True):
                demands: list[Demand] = []
                for p in properties:
                    need = self._need_at(
                        p, tier, flexible_pass, req, pledged, sacrifice
                    )
                    if need > EPS:
                        demands.append(
                            Demand(
                                key=p.id,
                                requirement_kwh=need,
                                weight=self._weight(p, tier, credits, config),
                            )
                        )
                if not demands or blocked:
                    continue
                share = weighted_max_min_fair(demands, remaining)
                used = math.fsum(share.values())
                if used <= 0.0:
                    continue
                for pid, kwh in share.items():
                    if kwh <= 0.0:
                        continue
                    granted[pid] += kwh
                    by_tier[pid][int(tier)] = by_tier[pid].get(int(tier), 0.0) + kwh
                remaining = max(0.0, remaining - used)
                if remaining <= EPS:
                    remaining = 0.0

        # ---- Credits: earned during scarcity, slowly decaying always.
        credits_delta: dict[str, float] = {}
        decay = _decay_fraction(req.duration_s, config.credit_decay_per_day)
        for p in properties:
            delta = 0.0
            if scarcity and sacrifice[p.id] > EPS:
                delta += sacrifice[p.id] * max(0.0, config.credit_earn_per_kwh)
            delta -= credits[p.id] * decay
            credits_delta[p.id] = delta

        # ---- Verdicts, reasons, history.
        alloc: dict[str, Alloc] = {}
        history_out: dict[str, PropertyHistory] = {}
        dt_h = (req.duration_s / 3600.0) if req.duration_s > 0 else 1.0

        for p in properties:
            g = granted[p.id]
            declared = p.declared_kwh()
            deferred_kwh = self._deferred_kwh(p, req)
            inflex_demand = declared - deferred_kwh
            shortfall = max(0.0, declared - g - sacrifice[p.id])

            granted_tiers = by_tier[p.id]
            lifeline_demand = p.declared_kwh_at((Tier.LIFE_HEALTH, Tier.BASIC))
            lifeline_got = granted_tiers.get(
                int(Tier.LIFE_HEALTH), 0.0
            ) + granted_tiers.get(int(Tier.BASIC), 0.0)
            comfort_demand = p.declared_kwh_at((Tier.PRODUCTIVE, Tier.COMFORT))
            comfort_got = granted_tiers.get(
                int(Tier.PRODUCTIVE), 0.0
            ) + granted_tiers.get(int(Tier.COMFORT), 0.0)

            state, reason, text = self._verdict(
                p=p,
                granted=g,
                declared=declared,
                inflex_demand=inflex_demand,
                shortfall=shortfall,
                sacrifice=sacrifice[p.id],
                spendable=spendable,
                capped=p.id in capped_ids,
                storage_blocked=any(l.tier in blocked_tiers for l in p.loads),
                lifeline_got=lifeline_got,
                lifeline_demand=lifeline_demand,
                comfort_got=comfort_got,
                comfort_demand=comfort_demand,
                has_flexible_left=deferred_kwh > EPS,
            )

            alloc[p.id] = Alloc(
                property_id=p.id,
                granted_energy_kwh=g,
                granted_power_kw=(g / dt_h) if dt_h > 0 else 0.0,
                state=state,
                reason_code=reason,
                reason_text=text,
                granted_by_tier=dict(by_tier[p.id]),
                score_breakdown={
                    "weight_t1": self._weight(p, Tier.LIFE_HEALTH, credits, config),
                    "weight_t2": self._weight(p, Tier.BASIC, credits, config),
                    "weight_t3": self._weight(p, Tier.PRODUCTIVE, credits, config),
                    "credits": credits[p.id],
                    "declared_kwh": declared,
                    "lifeline_kwh": p.lifeline_kwh,
                    "missing_kwh": shortfall,
                },
            )

            prev = req.history.get(p.id) or PropertyHistory()
            denied_streak = (
                prev.denied_streak + 1 if (g <= EPS and declared > EPS) else 0
            )
            if denied_streak >= config.starvation_cycles:
                extra = " while surplus remained" if remaining > EPS else ""
                warnings.append(
                    f"starvation warning: {p.id} denied {denied_streak} cycles in a row{extra}"
                )
            history_out[p.id] = PropertyHistory(
                denied_streak=denied_streak,
                granted_kwh_total=prev.granted_kwh_total + g,
                curtailment_cycles=prev.curtailment_cycles
                + (1 if sacrifice[p.id] > EPS else 0),
            )

        unserved_total = math.fsum(
            max(0.0, p.declared_kwh() - granted[p.id] - sacrifice[p.id])
            for p in properties
        )
        unserved_critical = math.fsum(
            max(
                0.0,
                p.declared_kwh_at((Tier.LIFE_HEALTH, Tier.BASIC))
                - by_tier[p.id].get(int(Tier.LIFE_HEALTH), 0.0)
                - by_tier[p.id].get(int(Tier.BASIC), 0.0),
            )
            for p in properties
        )

        return AllocResult(
            cycle_id=req.cycle_id,
            alloc=alloc,
            credits_delta=credits_delta,
            unserved_critical_kwh=unserved_critical,
            unserved_total_kwh=unserved_total,
            history_out=history_out,
            warnings=tuple(warnings),
            meta={
                "policy": f"{self.name}/{self.version}",
                "spendable_kwh": spendable,
                "declared_kwh": declared_total,
                "granted_kwh": math.fsum(granted.values()),
                "remaining_kwh": remaining,
                "scarcity": scarcity,
                "curtailed_kwh": math.fsum(sacrifice.values()),
                "reserve_blocked_tiers": sorted(int(t) for t in blocked_tiers),
            },
        )

    # --------------------------------------------------------------- internals
    @staticmethod
    def _storage_blocked(req: AllocRequest, fraction: float) -> bool:
        """True if the battery sits below the level a tier requires.

        Without a capacity in the request the rule cannot be evaluated, and no
        reserve applies. That is a deliberate choice, not a silent failure.
        """
        if req.storage_capacity_kwh <= 0.0 or fraction <= 0.0:
            return False
        soc = max(0.0, _safe_float(req.storage_soc_kwh))
        return soc < fraction * req.storage_capacity_kwh

    @staticmethod
    def _spendable(req: AllocRequest, config: Config) -> float:
        energy = max(0.0, _safe_float(req.available_energy_kwh))
        power = _safe_float(req.available_power_kw)
        if req.duration_s > 0 and power > 0.0:
            energy = min(energy, power * req.duration_s / 3600.0)
        margin = max(0.0, min(config.safety_margin, 0.5))
        return energy * (1.0 - margin)

    @staticmethod
    def _normalise(
        req: AllocRequest, config: Config, warnings: list[str]
    ) -> tuple[tuple[Property, ...], frozenset[str]]:
        seen: dict[str, Property] = {}
        for p in req.properties:
            if p.id in seen:
                warnings.append(f"duplicate property id '{p.id}' ignored")
                continue
            seen[p.id] = p

        capped: set[str] = set()
        out: list[Property] = []
        for pid in sorted(seen):
            p = seen[pid]
            clean: list[Load] = []
            for load in p.loads:
                if not is_finite(load.energy_kwh) or load.energy_kwh <= 0.0:
                    warnings.append(
                        f"{pid}: load '{load.name}' has invalid energy and is skipped"
                    )
                    continue
                clean.append(load)

            if p.historical_kwh_per_day > 0.0 and p.declared_kwh_per_day > 0.0:
                ratio = p.declared_kwh_per_day / p.historical_kwh_per_day
                if ratio > config.declaration_ratio_cap:
                    scale = config.declaration_ratio_cap / ratio
                    clean = [
                        replace(l, energy_kwh=l.energy_kwh * scale) for l in clean
                    ]
                    capped.add(pid)
                    warnings.append(
                        f"{pid}: declares {ratio:.1f}x its historical day, "
                        f"scaled to {config.declaration_ratio_cap:.1f}x"
                    )
            out.append(replace(p, loads=tuple(clean)))

        return tuple(out), frozenset(capped)

    @staticmethod
    def _is_flexible(load: Load, hour: float) -> bool:
        """Shiftable AND not past its deadline. Overdue loads become fixed."""
        if not load.shiftable:
            return False
        if load.deadline_hour is None:
            return True
        return hour < load.deadline_hour

    def _need_at(
        self,
        p: Property,
        tier: Tier,
        flexible_pass: bool,
        req: AllocRequest,
        pledged: frozenset[str],
        sacrifice: dict[str, float],
    ) -> float:
        need = 0.0
        for load in p.loads:
            if load.tier != tier:
                continue
            if self._is_flexible(load, req.hour_of_day) != flexible_pass:
                continue
            if tier in _CURTAILABLE_TIERS and p.id in pledged:
                sacrifice[p.id] += load.energy_kwh
                continue
            need += load.energy_kwh
        return need

    def _deferred_kwh(self, p: Property, req: AllocRequest) -> float:
        return sum(
            l.energy_kwh for l in p.loads if self._is_flexible(l, req.hour_of_day)
        )

    @staticmethod
    def _weight(
        p: Property, tier: Tier, credits: dict[str, float], config: Config
    ) -> float:
        weight = 1.0
        if tier in (Tier.LIFE_HEALTH, Tier.BASIC):
            for flag in p.vulnerability_flags:
                weight += config.vulnerability_bonus.get(flag, 0.0)
        if tier != Tier.LIFE_HEALTH:
            # Credits give a bounded advantage within your own tier. Never on
            # tier 1, never unbounded: nobody can buy their way past a critical
            # load.
            bonus = min(
                credits.get(p.id, 0.0) * max(0.0, config.credit_weight_per_unit),
                max(0.0, config.credit_weight_cap),
            )
            weight += max(0.0, bonus)
        return max(weight, 1e-6)

    def _verdict(
        self,
        *,
        p: Property,
        granted: float,
        declared: float,
        inflex_demand: float,
        shortfall: float,
        sacrifice: float,
        spendable: float,
        capped: bool,
        storage_blocked: bool,
        lifeline_got: float = 0.0,
        lifeline_demand: float = 0.0,
        comfort_got: float = 0.0,
        comfort_demand: float = 0.0,
        has_flexible_left: bool = False,
    ) -> tuple[State, ReasonCode, str]:
        if declared <= EPS:
            return (
                "granted",
                ReasonCode.CRITICALITY_ORDER,
                "no declared loads this cycle",
            )

        if _is_full(granted, declared):
            if _is_full(p.lifeline_kwh, declared):
                return (
                    "granted",
                    ReasonCode.LIFELINE_FLOOR,
                    "the whole requirement was life and basic need, and was met in full",
                )
            if sacrifice > EPS:
                return (
                    "granted",
                    ReasonCode.VOLUNTARY_CURTAILMENT,
                    f"curtailed {sacrifice:.2f} kWh of comfort voluntarily",
                )
            return (
                "granted",
                ReasonCode.CRITICALITY_ORDER,
                "the whole declared requirement was met, following the load ladder",
            )

        if sacrifice > EPS:
            state: State = "partial" if granted > EPS else "deferred"
            return (
                state,
                ReasonCode.VOLUNTARY_CURTAILMENT,
                f"curtailed {sacrifice:.2f} kWh of comfort voluntarily and earned credits",
            )

        if granted > EPS:
            # The case that is the entire point: need came first, comfort was shared.
            if _is_full(lifeline_got, lifeline_demand) and comfort_demand > EPS:
                if comfort_got <= EPS and has_flexible_left:
                    return (
                        "partial",
                        ReasonCode.DEFERRED_TO_STORAGE,
                        "life and basic need covered; shiftable load waiting for solar surplus",
                    )
                share = 100.0 * comfort_got / comfort_demand
                return (
                    "partial",
                    ReasonCode.CRITICALITY_ORDER,
                    f"life and basic need covered; comfort received {share:.0f} % of its need",
                )
            if granted >= inflex_demand * (1.0 - _REL_TOL) - EPS:
                return (
                    "partial",
                    ReasonCode.DEFERRED_TO_STORAGE,
                    f"everything except shiftable load covered; {shortfall:.3f} kWh moved to solar hours",
                )
            return (
                "partial",
                ReasonCode.PARTIAL_BUDGET,
                f"received {granted:.3f} of {declared:.3f} kWh — the budget ran out",
            )

        if capped:
            return (
                "denied",
                ReasonCode.OVER_DECLARED,
                "the declaration exceeded what is allowed and was scaled down",
            )
        if spendable <= EPS:
            return (
                "denied",
                ReasonCode.SUPPLY_UNAVAILABLE,
                "no power available in this cycle",
            )
        if storage_blocked:
            return (
                "deferred",
                ReasonCode.DEFERRED_TO_STORAGE,
                "holding the battery for the critical load tonight",
            )
        if inflex_demand <= EPS:
            return (
                "deferred",
                ReasonCode.DEFERRED_TO_STORAGE,
                "only shiftable load left; waiting for solar surplus",
            )
        return (
            "denied",
            ReasonCode.BUDGET_EXHAUSTED,
            f"denied: {shortfall:.3f} kWh of need, no energy left on this tier",
        )


def _is_full(got: float, wanted: float) -> bool:
    return got >= wanted - max(EPS, _FULL_TOL * abs(wanted))


def _safe_float(value: object) -> float:
    if not is_finite(value):
        return 0.0
    return float(value)  # type: ignore[arg-type]


def _decay_fraction(duration_s: int, decay_per_day: float) -> float:
    if duration_s <= 0 or decay_per_day <= 0.0:
        return 0.0
    d = min(max(decay_per_day, 0.0), 0.999)
    return 1.0 - (1.0 - d) ** (duration_s / 86400.0)
