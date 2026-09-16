"""Simulator: runs a policy against the barangay fixture over several days.

The simulator owns what the algorithm deliberately does not:

* battery physics (charge, discharge, efficiency, minimum state of charge)
* when households curtail their comfort voluntarily (the pledge rule)
* credit accounting over time
* the measurement

The algorithm only ever sees an `AllocRequest` and returns an `AllocResult`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from allocator.config import DEFAULT_CONFIG, Config
from allocator.fairness import gini
from allocator.models import (
    AllocRequest,
    AllocResult,
    Category,
    Load,
    Property,
    PropertyHistory,
    TIER_ORDER,
    Tier,
)
from allocator.policy import TieredNeedPolicy

from .scenario import (
    PropertySpec,
    build_barangay,
    cycles_in_window,
    in_window,
    solar_kw,
)

EPS = 1e-9


@dataclass(frozen=True)
class SimConfig:
    cycles_per_day: int = 96          # 15 minutes
    days: int = 3
    kwp: float = 14.0
    battery_kwh: float = 60.0
    battery_min_soc_fraction: float = 0.25
    battery_efficiency: float = 0.92
    max_charge_kw: float = 10.0
    max_discharge_kw: float = 10.0
    initial_soc_fraction: float = 0.6
    #: cloud factor per day. 1.0 = clear sky.
    cloud_by_day: tuple[float, ...] = (1.0, 0.7, 0.4)
    #: households switch off comfort voluntarily when the battery runs low in
    #: the evening
    pledge_soc_fraction: float = 0.35
    pledge_hours: tuple[float, float] = (17.0, 22.0)
    #: cycle to save as an example for the dashboard (None = none)
    sample_step: int | None = None
    seed: int = 7

    @property
    def duration_s(self) -> int:
        return int(round(86400 / self.cycles_per_day))

    @property
    def dt_h(self) -> float:
        return self.duration_s / 3600.0


@dataclass
class SimResult:
    policy: str
    steps: int
    generated_kwh: float = 0.0
    delivered_kwh: float = 0.0
    curtailed_kwh: float = 0.0
    unserved_total_kwh: float = 0.0
    unserved_critical_kwh: float = 0.0
    cycles_with_critical_unserved: int = 0
    tier1_declared_kwh: float = 0.0
    tier1_delivered_kwh: float = 0.0
    tier12_declared_kwh: float = 0.0
    tier12_delivered_kwh: float = 0.0
    comfort_declared_kwh: float = 0.0
    comfort_delivered_kwh: float = 0.0
    soc_min_kwh: float = math.inf
    soc_end_kwh: float = 0.0
    per_property_kwh: dict[str, float] = field(default_factory=dict)
    per_load_kwh: dict[str, float] = field(default_factory=dict)
    reason_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    sample_alloc: Mapping[str, object] | None = None
    credits_end: Mapping[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------- metrics
    @property
    def tier1_uptime(self) -> float:
        """Share of the life-and-health load that was actually delivered."""
        if self.tier1_declared_kwh <= 0:
            return 1.0
        return self.tier1_delivered_kwh / self.tier1_declared_kwh

    @property
    def tier12_uptime(self) -> float:
        if self.tier12_declared_kwh <= 0:
            return 1.0
        return self.tier12_delivered_kwh / self.tier12_declared_kwh

    @property
    def comfort_service(self) -> float:
        if self.comfort_declared_kwh <= 0:
            return 1.0
        return self.comfort_delivered_kwh / self.comfort_declared_kwh

    @property
    def unmet_fraction(self) -> float:
        total = self.delivered_kwh + self.unserved_total_kwh
        return (self.unserved_total_kwh / total) if total > 0 else 0.0

    def summary(self) -> dict[str, object]:
        return {
            "policy": self.policy,
            "critical_uptime_pct": round(100.0 * self.tier1_uptime, 2),
            "life_basic_uptime_pct": round(100.0 * self.tier12_uptime, 2),
            "comfort_service_pct": round(100.0 * self.comfort_service, 2),
            "unserved_critical_kwh": round(self.unserved_critical_kwh, 2),
            "unserved_total_kwh": round(self.unserved_total_kwh, 2),
            "cycles_without_critical_power": self.cycles_with_critical_unserved,
            "delivered_kwh": round(self.delivered_kwh, 1),
            "voluntarily_curtailed_kwh": round(self.curtailed_kwh, 1),
            "gini_delivered": round(gini(list(self.per_property_kwh.values())), 3),
        }


class Simulator:
    def __init__(
        self,
        specs: Iterable[PropertySpec],
        config: Config = DEFAULT_CONFIG,
        sim_config: SimConfig | None = None,
    ) -> None:
        self.specs: tuple[PropertySpec, ...] = tuple(specs)
        self.config = config
        self.cfg = sim_config or SimConfig()

    # ------------------------------------------------------------------- run
    def run(self, policy: TieredNeedPolicy) -> SimResult:
        cfg = self.cfg
        cpd = cfg.cycles_per_day
        steps = cpd * cfg.days
        result = SimResult(
            policy=getattr(policy, "name", type(policy).__name__), steps=steps
        )

        ledger: dict[tuple[str, str], float] = {}
        credits: dict[str, float] = {s.id: 0.0 for s in self.specs}
        history: dict[str, PropertyHistory] = {}
        soc = cfg.battery_kwh * cfg.initial_soc_fraction
        per_load_declared: dict[str, float] = {}

        for step in range(steps):
            hour = (step % cpd) * 24.0 / cpd
            if step % cpd == 0:
                ledger = {
                    (s.id, l.name): l.daily_kwh for s in self.specs for l in s.loads
                }
            day = step // cpd
            cloud = cfg.cloud_by_day[day % len(cfg.cloud_by_day)]

            gen_kw = solar_kw(hour, cfg.kwp, cloud)
            gen_kwh = gen_kw * cfg.dt_h
            min_soc = cfg.battery_kwh * cfg.battery_min_soc_fraction
            discharge_avail = min(
                max(0.0, soc - min_soc), cfg.max_discharge_kw * cfg.dt_h
            )

            properties = self._properties(hour, ledger, cpd)
            pledges = self._pledges(properties, soc, hour)

            req = AllocRequest(
                cycle_id=f"d{day}-{step % cpd:03d}",
                hour_of_day=hour,
                duration_s=cfg.duration_s,
                available_energy_kwh=gen_kwh + discharge_avail,
                available_power_kw=gen_kw + cfg.max_discharge_kw,
                properties=properties,
                credits=dict(credits),
                history=dict(history),
                curtailment_pledges=pledges,
                storage_soc_kwh=soc,
                storage_capacity_kwh=cfg.battery_kwh,
                is_islanded=True,
                t_start=f"day{day + 1}T{int(hour):02d}:{int((hour % 1) * 60):02d}",
            )
            res = policy.allocate(req, self.config)

            # --- measurement and accounting
            self._account(result, res, properties, ledger, per_load_declared)
            for pid, delta in res.credits_delta.items():
                credits[pid] = max(0.0, credits.get(pid, 0.0) + delta)
            history.update(res.history_out)
            result.warnings.extend(res.warnings[:3])

            # --- the battery
            used = res.total_granted_kwh()
            if used <= gen_kwh:
                surplus = gen_kwh - used
                room = max(0.0, cfg.battery_kwh - soc)
                charge = min(
                    surplus * cfg.battery_efficiency,
                    cfg.max_charge_kw * cfg.dt_h,
                    room,
                )
                soc += max(0.0, charge)
            else:
                deficit = used - gen_kwh
                soc -= min(soc, deficit / cfg.battery_efficiency)
                soc = max(0.0, soc)
            result.soc_min_kwh = min(result.soc_min_kwh, soc)

            if cfg.sample_step is not None and step == cfg.sample_step:
                result.sample_alloc = _dump_cycle(res, hour)

        result.soc_end_kwh = soc
        result.credits_end = dict(credits)
        if result.soc_min_kwh is math.inf:
            result.soc_min_kwh = soc
        return result

    # -------------------------------------------------------------- internal
    def _properties(
        self, hour: float, ledger: dict[tuple[str, str], float], cpd: int
    ) -> tuple[Property, ...]:
        out: list[Property] = []
        for s in self.specs:
            loads: list[Load] = []
            for ls in s.loads:
                remaining = ledger.get((s.id, ls.name), 0.0)
                if remaining <= EPS or not in_window(hour, ls.window):
                    continue
                if ls.shiftable:
                    past_deadline = ls.deadline is not None and hour >= ls.deadline
                    per_cycle = ls.daily_kwh / max(1, ls.spread_cycles)
                    energy = remaining if past_deadline else min(per_cycle, remaining)
                    loads.append(
                        Load(ls.name, ls.tier, energy, shiftable=True,
                             deadline_hour=ls.deadline)
                    )
                else:
                    cycles = cycles_in_window(ls.window, cpd)
                    per_cycle = ls.daily_kwh / max(1, cycles)
                    loads.append(Load(ls.name, ls.tier, min(per_cycle, remaining)))
            if not loads:
                continue
            out.append(
                Property(
                    id=s.id,
                    category=s.category,
                    occupants=s.occupants,
                    vulnerability_flags=s.vulnerability_flags,
                    loads=tuple(loads),
                    declared_kwh_per_day=s.declared_kwh_per_day,
                    historical_kwh_per_day=s.historical_kwh_per_day,
                )
            )
        return tuple(out)

    def _pledges(
        self, properties: tuple[Property, ...], soc: float, hour: float
    ) -> frozenset[str]:
        cfg = self.cfg
        if not (cfg.pledge_hours[0] <= hour < cfg.pledge_hours[1]):
            return frozenset()
        if soc >= cfg.pledge_soc_fraction * cfg.battery_kwh:
            return frozenset()
        return frozenset(
            p.id
            for p in properties
            if p.category is Category.HOUSEHOLD
            and any(l.tier is Tier.COMFORT for l in p.loads)
        )

    @staticmethod
    def _account(
        result: SimResult,
        res: AllocResult,
        properties: tuple[Property, ...],
        ledger: dict[tuple[str, str], float],
        per_load_declared: dict[str, float],
    ) -> None:
        result.generated_kwh += float(res.meta.get("spendable_kwh", 0.0))
        result.delivered_kwh += res.total_granted_kwh()
        result.curtailed_kwh += float(res.meta.get("curtailed_kwh", 0.0))
        result.unserved_total_kwh += res.unserved_total_kwh
        result.unserved_critical_kwh += res.unserved_critical_kwh
        if res.unserved_critical_kwh > EPS:
            result.cycles_with_critical_unserved += 1

        for a in res.alloc.values():
            result.per_property_kwh[a.property_id] = (
                result.per_property_kwh.get(a.property_id, 0.0) + a.granted_energy_kwh
            )
            result.reason_counts[a.reason_code.value] = (
                result.reason_counts.get(a.reason_code.value, 0) + 1
            )

        for p in properties:
            a = res.alloc.get(p.id)
            if a is None:
                continue
            delivered = _attribute(p, a)
            for load in p.loads:
                key = (p.id, load.name)
                per_load_declared[load.name] = (
                    per_load_declared.get(load.name, 0.0) + load.energy_kwh
                )
                result.per_load_kwh[load.name] = (
                    result.per_load_kwh.get(load.name, 0.0)
                    + delivered.get(load.name, 0.0)
                )
                ledger[key] = max(
                    0.0, ledger.get(key, 0.0) - delivered.get(load.name, 0.0)
                )
                if load.tier is Tier.LIFE_HEALTH:
                    result.tier1_declared_kwh += load.energy_kwh
                    result.tier1_delivered_kwh += delivered.get(load.name, 0.0)
                if load.tier in (Tier.LIFE_HEALTH, Tier.BASIC):
                    result.tier12_declared_kwh += load.energy_kwh
                    result.tier12_delivered_kwh += delivered.get(load.name, 0.0)
                if load.tier is Tier.COMFORT:
                    result.comfort_declared_kwh += load.energy_kwh
                    result.comfort_delivered_kwh += delivered.get(load.name, 0.0)


def _attribute(p: Property, alloc) -> dict[str, float]:
    """Spread a property's allocation across its loads, tier by tier. The
    allocation arrived per tier from the policy, so this is exact."""
    out: dict[str, float] = {}
    for tier in TIER_ORDER:
        grant = float(alloc.granted_by_tier.get(int(tier), 0.0))
        if grant <= EPS:
            continue
        left = grant
        for load in p.loads:
            if load.tier is not tier or left <= EPS:
                continue
            take = min(load.energy_kwh, left)
            out[load.name] = out.get(load.name, 0.0) + take
            left -= take
    return out


def _dump_cycle(res: AllocResult, hour: float) -> dict[str, object]:
    """Exactly the JSON a dashboard consumes. The UI needs nothing more."""
    return {
        "cycle": res.cycle_id,
        "time": f"{int(hour):02d}:{int((hour % 1) * 60):02d}",
        "budget_kwh": round(float(res.meta.get("spendable_kwh", 0.0)), 3),
        "scarcity": bool(res.meta.get("scarcity", False)),
        "properties": [
            {
                "id": a.property_id,
                "received_kwh": round(a.granted_energy_kwh, 3),
                "status": a.state,
                "reason": a.reason_code.value,
                "explanation": a.reason_text,
                "by_tier": {
                    str(k): round(v, 3) for k, v in a.granted_by_tier.items()
                },
            }
            for a in sorted(
                res.alloc.values(),
                key=lambda x: (0 if x.state != "granted" else 1, x.property_id),
            )
            if a.granted_energy_kwh > 0 or a.state != "granted"
        ],
    }


def run_comparison(
    specs: Iterable[PropertySpec] | None = None,
    config: Config = DEFAULT_CONFIG,
    sim_config: SimConfig | None = None,
    policies: Mapping[str, object] | None = None,
) -> dict[str, SimResult]:
    from allocator.baselines import BASELINES

    specs = tuple(specs) if specs is not None else build_barangay()
    sim_config = sim_config or SimConfig()
    if policies is None:
        policies = {
            "load ladder (ours)": TieredNeedPolicy(),
            **{name: cls() for name, cls in BASELINES.items()},
        }

    out: dict[str, SimResult] = {}
    for name, policy in policies.items():
        sim = Simulator(specs, config, sim_config)
        out[name] = sim.run(policy)  # type: ignore[arg-type]
    return out
