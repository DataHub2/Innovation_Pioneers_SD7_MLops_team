"""Command line interface. Runs a demo of the whole chain.

    python -m harness.cli --days 3 --sample
    python -m harness.cli --days 3 --json out.json
"""

from __future__ import annotations

import argparse
import sys

from allocator.baselines import BASELINES
from allocator.policy import TieredNeedPolicy

from .report import print_comparison, sample_cycle_report, to_json
from .scenario import build_barangay
from .simulate import SimConfig, Simulator

OURS = "load ladder (ours)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run the allocation algorithm against the barangay fixture."
    )
    p.add_argument("--days", type=int, default=3, help="number of days to simulate")
    p.add_argument("--kwp", type=float, default=20.0, help="solar array size in kWp")
    p.add_argument("--battery", type=float, default=80.0, help="battery size in kWh")
    p.add_argument(
        "--cycles-per-day",
        type=int,
        default=96,
        help="timesteps per day (96 = 15 minutes)",
    )
    p.add_argument("--households", type=int, default=24, help="number of households")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument(
        "--cloud",
        type=str,
        default="1.0,0.7,0.4",
        help="cloud factor per day, e.g. '1.0,0.7,0.4'",
    )
    p.add_argument("--json", type=str, default=None, help="write results to JSON")
    p.add_argument(
        "--sample",
        action="store_true",
        help="show a single cycle with reasons (dashboard preview)",
    )
    p.add_argument(
        "--only",
        type=str,
        default=None,
        help="run this policy only (ours, " + ", ".join(BASELINES) + ")",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    specs = build_barangay(n_households=args.households, seed=args.seed)
    cloud = tuple(float(x) for x in args.cloud.split(","))
    sim_cfg = SimConfig(
        cycles_per_day=args.cycles_per_day,
        days=args.days,
        kwp=args.kwp,
        battery_kwh=args.battery,
        cloud_by_day=cloud,
        sample_step=(
            args.cycles_per_day * (args.days - 1)
            + int(args.cycles_per_day * 20.5 / 24)
        )
        if args.sample
        else None,
        seed=args.seed,
    )

    policies: dict[str, object] = {OURS: TieredNeedPolicy()}
    policies.update({name: cls() for name, cls in BASELINES.items()})
    if args.only:
        key = OURS if args.only in ("ours", "ladder") else args.only
        if key not in policies:
            print(f"unknown policy: {args.only}", file=sys.stderr)
            return 2
        policies = {key: policies[key]}

    daily_demand = sum(s.declared_kwh_per_day for s in specs)
    print(
        f"Barangay: {len(specs)} properties, declared demand "
        f"{daily_demand:.1f} kWh/day, solar {args.kwp} kWp, battery {args.battery} kWh"
    )
    print(f"Period: {args.days} days, {args.cycles_per_day} steps/day, cloud {cloud}\n")

    results: dict[str, object] = {}
    for name, policy in policies.items():
        sim = Simulator(specs, sim_config=sim_cfg)
        results[name] = sim.run(policy)  # type: ignore[arg-type]

    print_comparison(results)  # type: ignore[arg-type]

    if args.sample:
        print()
        print(sample_cycle_report(results))  # type: ignore[arg-type]

    if args.json:
        p = to_json(results, args.json)  # type: ignore[arg-type]
        print(f"\nJSON written to {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
