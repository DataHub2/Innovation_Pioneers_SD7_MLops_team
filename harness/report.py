"""Reporting: comparison table, JSON export and a single-cycle view.

The JSON export is the contract with the dashboard. Your dashboard reads it, and
if someone later builds another dashboard it reads the same file. The algorithm
never has to change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .simulate import SimResult

COLUMNS: tuple[tuple[str, str], ...] = (
    ("policy", "policy"),
    ("critical_uptime_pct", "critical power %"),
    ("life_basic_uptime_pct", "life+basic %"),
    ("comfort_service_pct", "comfort %"),
    ("unserved_critical_kwh", "unserved critical"),
    ("cycles_without_critical_power", "cycles without"),
    ("delivered_kwh", "delivered kWh"),
    ("gini_delivered", "gini"),
)


def comparison_table(results: Mapping[str, SimResult]) -> str:
    rows = [res.summary() for res in results.values()]
    widths: list[int] = []
    for key, title in COLUMNS:
        w = max(len(title), *(len(str(r.get(key, ""))) for r in rows))
        widths.append(w)

    def line(values: list[str]) -> str:
        return "  ".join(v.ljust(w) for v, w in zip(values, widths))

    out = [line([t for _, t in COLUMNS])]
    out.append("-" * len(out[0]))
    for r in rows:
        out.append(line([str(r.get(k, "")) for k, _ in COLUMNS]))
    return "\n".join(out)


def print_comparison(results: Mapping[str, SimResult]) -> None:
    print(comparison_table(results))


def sample_cycle_report(results: Mapping[str, SimResult], limit: int = 12) -> str:
    """Show what a single decision looks like, with its reason. This is what a
    jury remembers: the algorithm can explain itself."""
    for res in results.values():
        if res.sample_alloc is None:
            continue
        data = res.sample_alloc
        out = [
            f"Cycle {data['cycle']} at {data['time']} — "
            f"budget {data['budget_kwh']} kWh, scarcity: {data['scarcity']}",
            f"policy: {res.policy}",
            "",
        ]
        for row in list(data["properties"])[:limit]:  # type: ignore[index]
            out.append(
                f"  {row['id']:<14} {row['received_kwh']:>6.3f} kWh  "
                f"{row['status']:<9} {row['reason']:<22} {row['explanation']}"
            )
        return "\n".join(out)
    return "(no sample cycle captured — run with --sample)"


def to_json(results: Mapping[str, SimResult], path: str | Path) -> Path:
    p = Path(path)
    payload = {
        "summary": [res.summary() for res in results.values()],
        "details": {
            name: {
                "policy": res.policy,
                "steps": res.steps,
                "kwh_per_property": {
                    k: round(v, 4) for k, v in res.per_property_kwh.items()
                },
                "kwh_per_load": {k: round(v, 4) for k, v in res.per_load_kwh.items()},
                "reasons": res.reason_counts,
                "warnings": res.warnings[:50],
                "sample_cycle": res.sample_alloc,
            }
            for name, res in results.items()
        },
    }
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
