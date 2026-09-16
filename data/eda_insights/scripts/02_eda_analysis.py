#!/usr/bin/env python3
"""Reproducible EDA for data/people-without-electricity-country.csv.

Run from the repository root:

    python data/eda_insights/scripts/02_eda_analysis.py

Writes CSV/JSON to data/eda_insights/outputs/ and PNG to data/eda_insights/figures/.
Standard library + pandas + numpy + matplotlib only.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "people-without-electricity-country.csv"
OUT = ROOT / "data" / "eda_insights" / "outputs"
FIG = ROOT / "data" / "eda_insights" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

VALUE = "Number of people without access to electricity"
AGG_PREFIXES = ("OWID_", "WB_")

# --------------------------------------------------------------------- load
raw = pd.read_csv(SRC).rename(columns={VALUE: "deficit"})
raw["is_aggregate"] = raw["Code"].str.startswith(AGG_PREFIXES)
countries = raw[~raw["is_aggregate"]].copy()

world = raw.loc[raw["Code"] == "OWID_WRL"].set_index("Year")["deficit"]
regional = raw[raw["Code"].str.startswith("WB_")]
region_panel = regional.pivot_table(index="Year", columns="Entity", values="deficit")

# `deficit` is integer-valued in the source; keep it as float because a few
# rows carry a .5 (the World Bank interpolates), but never treat those as exact.
summary: dict[str, object] = {}

# ---------------------------------------------------------- 1. data profile
summary["rows"] = int(len(raw))
summary["entities_total"] = int(raw["Entity"].nunique())
summary["entities_countries"] = int(countries["Entity"].nunique())
summary["entities_aggregates"] = int(raw.loc[raw["is_aggregate"], "Entity"].nunique())
summary["aggregate_list"] = sorted(raw.loc[raw["is_aggregate"], "Entity"].unique().tolist())
summary["year_min"] = int(raw["Year"].min())
summary["year_max"] = int(raw["Year"].max())
summary["n_years"] = int(raw["Year"].nunique())
summary["null_cells"] = int(raw[["Entity", "Code", "Year", "deficit"]].isna().sum().sum())
summary["zero_cells"] = int((raw["deficit"] == 0).sum())
summary["zero_share_pct"] = round(100.0 * (raw["deficit"] == 0).mean(), 2)
summary["negative_cells"] = int((raw["deficit"] < 0).sum())

all_zero = raw.groupby("Code")["deficit"].max()
summary["entities_always_zero"] = int((all_zero == 0).sum())

# Coverage: how many entities report in each year (drives the 1990 artifact).
coverage = raw.groupby("Year")["Code"].nunique()
summary["coverage_first_year"] = {int(y): int(coverage.loc[y]) for y in (1990, 1995, 2000, 2010, 2024)}

# Latest observation per country.
idx = countries.groupby("Code")["Year"].idxmax()
latest = countries.loc[idx].sort_values("deficit", ascending=False).reset_index(drop=True)
latest[["Entity", "Code", "Year", "deficit"]].to_csv(OUT / "latest_per_country.csv", index=False)
summary["latest_year_counts"] = {int(k): int(v) for k, v in latest["Year"].value_counts().items()}

# ------------------------------------------------- 2. corrected ranking + bug
buggy = raw[~raw["Code"].str.startswith("OWID_")].copy()
buggy_idx = buggy.groupby("Code")["Year"].idxmax()
buggy_top15 = buggy.loc[buggy_idx].sort_values("deficit", ascending=False).head(15)

fixed_top15 = latest.head(15).copy()
fixed_top15["rank"] = range(1, len(fixed_top15) + 1)
fixed_top15[["rank", "Entity", "Code", "Year", "deficit"]].to_csv(
    OUT / "corrected_top15.csv", index=False
)

summary["buggy_top15_sum"] = int(buggy_top15["deficit"].sum())
summary["corrected_top15_sum"] = int(fixed_top15["deficit"].sum())
summary["bug_overstatement_pct"] = round(
    100.0 * (summary["buggy_top15_sum"] / summary["corrected_top15_sum"] - 1.0), 1
)
summary["bug_aggregates_leaking_through"] = buggy_top15.loc[
    buggy_top15["Code"].str.startswith("WB_"), "Entity"
].tolist()

# ------------------------------------------------------ 3. global trajectory
glob = pd.DataFrame(
    {
        "world_reported": world,
        "sum_of_countries": countries.groupby("Year")["deficit"].sum(),
        "entities_reporting": countries.groupby("Year")["Code"].nunique(),
    }
).sort_index()
glob.to_csv(OUT / "global_timeseries.csv")
summary["world_2023"] = int(world.loc[2023])
summary["world_2024"] = int(world.loc[2024])
summary["sum_countries_2024"] = int(glob.loc[2024, "sum_of_countries"])

# ------------------------------------------- 4. regional decomposition (WB)
reg_last = region_panel.loc[2024].sort_values(ascending=False)
reg_share = (region_panel.loc[2024] / world.loc[2024] * 100).reindex(reg_last.index)
region_panel.to_csv(OUT / "regional_breakdown.csv")
summary["ssa_share_2000_pct"] = round(float(region_panel.loc[2000].get("Sub-Saharan Africa (WB)", np.nan) / world.loc[2000] * 100), 1)
summary["ssa_share_2024_pct"] = round(float(region_panel.loc[2024].get("Sub-Saharan Africa (WB)", np.nan) / world.loc[2024] * 100), 1)

# ------------------------------------------------ 5. concentration over time
conc = []
for year in (2000, 2010, 2017, 2024):
    s = countries.loc[countries["Year"] == year, "deficit"].sort_values(ascending=False)
    tot = s.sum()
    xs = np.sort(s.values)
    n = len(xs)
    gini = (2.0 * np.sum(np.arange(1, n + 1) * xs)) / (n * xs.sum()) - (n + 1.0) / n
    conc.append(
        {
            "year": year,
            "n_entities": int(n),
            "top1_pct": round(100 * s.iloc[0] / tot, 2),
            "top5_pct": round(100 * s.head(5).sum() / tot, 2),
            "top10_pct": round(100 * s.head(10).sum() / tot, 2),
            "top20_pct": round(100 * s.head(20).sum() / tot, 2),
            "hhi": round(float(((s / tot) ** 2).sum()), 4),
            "gini": round(float(gini), 4),
        }
    )
pd.DataFrame(conc).to_csv(OUT / "concentration.csv", index=False)

# ----------------------------------------- 6. movers: improvers / worseners
panel = countries.pivot_table(index="Code", columns="Year", values="deficit")
names = countries.drop_duplicates("Code").set_index("Code")["Entity"]


def movers(y0: int, y1: int) -> pd.DataFrame:
    sub = panel[[y0, y1]].dropna().copy()
    sub["delta"] = sub[y1] - sub[y0]
    sub["pct_change"] = np.where(sub[y0] > 0, 100 * sub["delta"] / sub[y0], np.nan)
    sub["Entity"] = names.reindex(sub.index)
    return sub


m0024 = movers(2000, 2024).sort_values("delta")
m0024.to_csv(OUT / "movers_2000_2024.csv")
m1024 = movers(2010, 2024)
m1024.sort_values("delta").to_csv(OUT / "movers_2010_2024.csv")
worse = m1024[m1024["delta"] > 0].sort_values("delta", ascending=False)
summary["countries_worse_2010_2024"] = int(len(worse))
summary["people_added_by_worsening_countries"] = int(worse["delta"].sum())

# ------------------------------------------------- 7. pace and 2030 outlook
s = glob["sum_of_countries"]
rates = {}
for a, b in ((2000, 2010), (2010, 2024)):
    rates[f"{a}_{b}"] = round(100 * ((s[b] / s[a]) ** (1 / (b - a)) - 1), 2)
summary["annual_change_pct"] = rates
r = (s[2010] / s[2024]) ** (1 / 14) - 1
summary["projection_2030_at_2010_2024_pace"] = int(s[2024] * ((1 - r) ** 6))
summary["projection_2030_note"] = (
    "Linear-in-log extrapolation of the 2010-2024 average annual decline. "
    "Optimistic: assumes every country keeps its recent pace."
)

# --------------------------------------------------------- 8. cross-checks
summary["crosscheck_method_md"] = {
    "world_2023_from_csv": int(world.loc[2023]),
    "world_2023_claimed_in_METHOD_md": 677_000_000,
    "philippines_2023_from_csv": int(
        raw.loc[(raw["Code"] == "PHL") & (raw["Year"] == 2023), "deficit"].iloc[0]
    ),
    "philippines_2023_claimed_in_METHOD_md": 2_300_000,
    "verdict": "The pitch figures in docs/METHOD.md 8.2 reproduce from this file.",
}

(OUT / "summary_metrics.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)

# ------------------------------------------------------------- 9. figures
plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.25, "axes.spines.top": False,
                     "axes.spines.right": False})
ACC = "#c1121f"

# Fig 1 — global trajectory + coverage caution
fig, ax = plt.subplots(figsize=(7.2, 3.6))
ax.plot(glob.index, glob["sum_of_countries"] / 1e6, color=ACC, lw=2,
        label="Sum of countries")
ax.plot(glob.index, glob["world_reported"] / 1e6, color="#444", lw=1.2, ls="--",
        label="World (OWID aggregate)")
ax.axvspan(1990, 2000, color="#999", alpha=0.18)
ax.annotate("incomplete panel:\nonly 96 entities\nreport in 1990",
            xy=(1991, 119), xytext=(1993.5, 480), fontsize=7.5,
            arrowprops=dict(arrowstyle="->", lw=0.8))
ax.set_ylabel("people without electricity (millions)")
ax.set_xlabel("year")
ax.set_title("Global access deficit, 1990-2024 — with the coverage caveat shaded")
ax.legend(frameon=False, fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "fig1_global_trajectory.png")
plt.close(fig)

# Fig 2 — where the problem now sits
fig, ax = plt.subplots(figsize=(7.2, 3.2))
lbl = [t.replace(" (WB)", "") for t in reg_last.index]
vals = reg_last.values / 1e6
bars = ax.barh(lbl[::-1], vals[::-1], color=[ACC] + ["#8d99ae"] * (len(vals) - 1))
for b, v in zip(bars, vals[::-1]):
    ax.text(b.get_width() + 6, b.get_y() + b.get_height() / 2, f"{v:,.0f} M",
            va="center", fontsize=8)
ax.set_xlabel("people without electricity, 2024 (millions)")
ax.set_title("88 % of the world's access deficit is now in Sub-Saharan Africa")
ax.set_xlim(0, 660)
fig.tight_layout()
fig.savefig(FIG / "fig2_regional_2024.png")
plt.close(fig)

# Fig 3 — corrected top 15 vs the contaminated one
fig, ax = plt.subplots(figsize=(7.2, 4.4))
t = fixed_top15.head(15)
colors = [ACC if c not in summary["bug_aggregates_leaking_through"] else "#8d99ae"
          for c in t["Entity"]]
ax.barh(t["Entity"][::-1], t["deficit"][::-1] / 1e6, color=colors[::-1])
ax.set_xlabel("people without electricity, latest year (millions)")
ax.set_title("Corrected top 15 countries — no regional aggregates")
fig.tight_layout()
fig.savefig(FIG / "fig3_top15_corrected.png")
plt.close(fig)

# Fig 4 — concentration
fig, ax = plt.subplots(figsize=(7.2, 3.2))
cd = pd.DataFrame(conc)
for col, lab in (("top1_pct", "largest country"), ("top5_pct", "top 5"),
                 ("top10_pct", "top 10"), ("top20_pct", "top 20")):
    ax.plot(cd["year"], cd[col], marker="o", ms=3.5, lw=1.6, label=lab)
ax.set_ylabel("% of global deficit")
ax.set_xlabel("year")
ax.set_title("Concentration of the deficit is falling — the problem is spreading, not shrinking")
ax.legend(frameon=False, fontsize=8, ncol=2)
ax.set_ylim(0, 100)
fig.tight_layout()
fig.savefig(FIG / "fig4_concentration.png")
plt.close(fig)

# Fig 5 — decomposition: what drove the change since 2000
fig, ax = plt.subplots(figsize=(7.2, 3.6))
mm = m0024.copy()
top_fall = mm.nsmallest(5, "delta")
top_rise = mm.nlargest(5, "delta")
sel = pd.concat([top_fall, top_rise]).sort_values("delta")
col = [ACC if d > 0 else "#2a9d8f" for d in sel["delta"]]
ax.barh(sel["Entity"][::-1], (sel["delta"] / 1e6)[::-1], color=col[::-1])
ax.axvline(0, color="#333", lw=0.9)
ax.set_xlabel("change in people without electricity, 2000 → 2024 (millions)")
ax.set_title("Five success stories and five countries going backwards")
fig.tight_layout()
fig.savefig(FIG / "fig5_movers.png")
plt.close(fig)

print("wrote outputs to", OUT)
print("wrote figures to", FIG)
print(json.dumps({k: summary[k] for k in (
    "rows", "entities_countries", "bug_overstatement_pct",
    "ssa_share_2024_pct", "projection_2030_at_2010_2024_pace")}, indent=2))
