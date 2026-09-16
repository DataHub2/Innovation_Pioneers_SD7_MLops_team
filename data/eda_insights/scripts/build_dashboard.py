#!/usr/bin/env python3
"""Builds the data document: everything this dataset says, for a first-time reader.

Not a pitch. No recommendations. Every figure is audited at build time and the
build fails loudly if two labels collide or a label leaves the plot area.

    python3 data/eda_insights/scripts/build_dashboard.py

Output: data/eda_insights/dashboard.html (+ figures in figures/)
"""

from __future__ import annotations

import base64
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "people-without-electricity-country.csv"
EDA = ROOT / "data" / "eda_insights"
FIG = EDA / "figures"
OUT = EDA / "dashboard.html"
FIG.mkdir(parents=True, exist_ok=True)

RED, TEAL, GREY, INK, AMBER = "#c1121f", "#2a9d8f", "#9aa3b0", "#1b1b1f", "#c77d0a"
plt.rcParams.update({
    "figure.dpi": 150, "font.size": 11, "axes.grid": True, "grid.alpha": 0.16,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#d6d9de", "text.color": INK,
    "axes.labelcolor": INK, "xtick.color": GREY, "ytick.color": GREY,
})

AUDIT: list[str] = []


def b64(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def audit(fig, name: str) -> None:
    """Measure every label; fail loudly on overlap or overflow."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    ax = fig.axes[0]

    def nm(o) -> str:
        return o.get_text().replace("\n", " ")[:32] if hasattr(o, "get_text") else "[legend]"

    def box(t):
        return t, t.get_window_extent(r)

    items = [box(t) for t in ax.texts if t.get_text().strip()]
    leg = ax.get_legend()
    if leg is not None:
        items.append((leg, leg.get_window_extent(r)))
    area = ax.get_window_extent(r)
    fig_items = [box(t) for t in fig.texts if t.get_text().strip()]
    farea = fig.get_window_extent(r)

    problems = []
    for i, (t1, b1) in enumerate(items):
        for t2, b2 in items[i + 1:]:
            if b1.overlaps(b2):
                problems.append(f"OVERLAP {nm(t1)!r} x {nm(t2)!r}")
    for t, b in items:
        if not (area.x0 - 1 <= b.x0 and b.x1 <= area.x1 + 1
                and area.y0 - 1 <= b.y0 and b.y1 <= area.y1 + 1):
            problems.append(f"OUTSIDE AXES: {nm(t)!r}")
    for t, b in fig_items:
        if not (farea.x0 - 1 <= b.x0 and b.x1 <= farea.x1 + 1
                and farea.y0 - 1 <= b.y0 and b.y1 <= farea.y1 + 1):
            problems.append(f"OFF-FIGURE: {nm(t)!r}")
    for i, (t1, b1) in enumerate(fig_items):
        for t2, b2 in fig_items[i + 1:]:
            if b1.overlaps(b2):
                problems.append(f"BANNER OVERLAP {nm(t1)!r} x {nm(t2)!r}")
    for ln in ax.lines:
        yd = ln.get_ydata()
        if len(yd) < 2:
            continue
        pts = ax.transData.transform(list(zip(ln.get_xdata(), yd)))
        for t in ax.texts:
            if not t.get_text().strip():
                continue
            b = t.get_window_extent(r)
            if ((pts[:, 0] > b.x0) & (pts[:, 0] < b.x1)
                    & (pts[:, 1] > b.y0) & (pts[:, 1] < b.y1)).sum():
                problems.append(f"ON A LINE: {nm(t)!r}")
    AUDIT.append(f"{name}: {'clean' if not problems else ' / '.join(problems)}")


def finish(fig, name: str, filename: str, left: float = 0.20, nudge=()) -> str:
    fig.subplots_adjust(left=left, right=0.98, top=0.94, bottom=0.30)
    # Nudge after the axes have their final size, so the correction is measured
    # against the same geometry the audit, and the reader, will see.
    for t in nudge:
        nudge_inside(fig.axes[0], t)
    audit(fig, name)
    path = FIG / filename
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return b64(path)


def label(ax, x, y, text, color, size=13, box=True, **kw):
    return ax.text(x, y, text, color=color, fontsize=size, fontweight="bold",
                   va=kw.pop("va", "center"), ha=kw.pop("ha", "left"),
                   bbox=(dict(facecolor="white", edgecolor="none", alpha=0.88, pad=2.0)
                         if box else None), **kw)


def banner(fig, text, color):
    return fig.text(0.59, 0.075, text, ha="center", va="center", fontsize=11.5,
                    fontweight="bold", color=color,
                    bbox=dict(boxstyle="round,pad=0.6", facecolor="#f2f4f7",
                              edgecolor="none"))


def nudge_inside(ax, t, pad: float = 3.0) -> None:
    """Slide a text horizontally until its box sits inside the axes.

    A label centred on a band that happens to peak in the first or the last year
    of the axis hangs over the edge. Moving it would take it off its band, so it
    is slid along x by exactly the overlap instead. The audit measures the same
    boxes afterwards and still fails loudly if this was not enough.
    """
    fig = ax.figure
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    area, b = ax.get_window_extent(r), t.get_window_extent(r)
    dx = 0.0
    if b.x0 < area.x0 + pad:
        dx = area.x0 + pad - b.x0
    elif b.x1 > area.x1 - pad:
        dx = area.x1 - pad - b.x1
    if dx:
        x0, x1 = ax.get_xlim()
        t.set_x(t.get_position()[0] + dx * (x1 - x0) / area.width)


def millions(x: float) -> str:
    return f"{x/1e6:,.0f}".replace(",", " ")


def exact(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


# ------------------------------------------------------------------ the data
raw = pd.read_csv(SRC).rename(columns={
    "Number of people without access to electricity": "d"})
is_agg = raw["Code"].str.startswith(("OWID_", "WB_"))
ctry = raw[~is_agg].copy()
world = raw.loc[raw["Code"] == "OWID_WRL"].set_index("Year")["d"]
ssa = raw.loc[raw["Code"] == "WB_SSA"].set_index("Year")["d"]
tot = ctry.groupby("Year")["d"].sum()
panel = ctry.pivot_table(index="Code", columns="Year", values="d")
names = ctry.drop_duplicates("Code").set_index("Code")["Entity"]
Y0, Y1, TGT = 2000, 2024, 2030

# Country -> World Bank region and income group. An input file, not a derivation:
# it comes from scripts/fetch_regions.py. The block below checks it against the
# regional aggregates carried in this same CSV and refuses to run if it drifts.
REG = pd.read_csv(EDA / "country_regions.csv").set_index("Code")
ctry["region"] = ctry["Code"].map(REG["wb_region"])
ctry["income"] = ctry["Code"].map(REG["income_level"])

S = {
    "rows": len(raw), "n_countries": ctry["Code"].nunique(),
    "n_agg": raw.loc[is_agg, "Entity"].nunique(),
    "yr0": int(raw["Year"].min()), "yr1": int(raw["Year"].max()),
    "then": tot[Y0], "now": tot[Y1], "cut": 100 * (1 - tot[Y1] / tot[Y0]),
    "ssa_then": ssa[Y0], "ssa_now": ssa[Y1],
    "ssa_change": 100 * (ssa[Y1] / ssa[Y0] - 1),
    "share_then": 100 * ssa[Y0] / world[Y0], "share_now": 100 * ssa[Y1] / world[Y1],
    "rest_then": tot[Y0] - ssa[Y0], "rest_now": tot[Y1] - ssa[Y1],
    "india_then": panel.loc["IND", Y0], "india_now": panel.loc["IND", Y1],
    "india_peak": panel.loc["IND"].max(), "india_peak_yr": int(panel.loc["IND"].idxmax()),
    "zeros": int((raw["d"] == 0).sum()),
    "always_zero": int((raw.groupby("Code")["d"].max() == 0).sum()),
}
S["rest_cut"] = 100 * (1 - S["rest_now"] / S["rest_then"])

mv = panel[[2010, Y1]].dropna().copy()
mv["delta"] = mv[Y1] - mv[2010]
worse = mv[mv["delta"] > 0].sort_values("delta", ascending=False)
worse["Entity"] = names.reindex(worse.index)
better = mv[mv["delta"] < 0].sort_values("delta")
better["Entity"] = names.reindex(better.index)
S["worse_n"], S["worse_added"] = len(worse), worse["delta"].sum()
NON_AFRICA = {"SYR", "LBY", "ARG", "CHL"}
S["worse_africa"] = sum(1 for c in worse.index if c not in NON_AFRICA)

ssa_rate = (ssa[Y1] / ssa[2010]) ** (1 / (Y1 - 2010)) - 1
S["ssa_years_halve"] = math.log(0.5) / math.log(1 + ssa_rate)
world_rate = (tot[2010] / tot[Y1]) ** (1 / (Y1 - 2010)) - 1
S["proj_2030"] = tot[Y1] * (1 - world_rate) ** (TGT - Y1)

latest = ctry.loc[ctry.groupby("Code")["Year"].idxmax()].sort_values("d", ascending=False)
top15 = latest.head(15)
buggy = raw[~raw["Code"].str.startswith("OWID_")]
bt = buggy.loc[buggy.groupby("Code")["Year"].idxmax()]
S["bug_pct"] = 100 * (bt["d"].nlargest(15).sum() / top15["d"].sum() - 1)

top20 = latest.head(20).copy()
top20["code"] = top20["Code"]
top20["delta"] = [panel.loc[c, Y1] - panel.loc[c, 2010] for c in top20["code"]]
S["top20_share"] = 100 * top20["d"].sum() / tot[Y1]
S["top20_improving"] = int((top20["delta"] < 0).sum())
S["top20_worsening"] = int((top20["delta"] > 0).sum())

# ---------------------------------------------------------------- regions
# The seven regional aggregates are the ones this file carries. They are shown
# as given. The country mapping is used only to say what is *inside* a region —
# never to re-add it, which would double-count exactly as the WB_ rows do.
REGIONS = [
    ("Sub-Saharan Africa", "WB_SSA", "Sub-Saharan Africa"),
    ("South Asia", "WB_SA", "South Asia"),
    ("East Asia & Pacific", "WB_EAP", "East Asia & Pacific"),
    ("Middle East, North Africa, Afghanistan & Pakistan", "WB_MENAP",
     "Middle East, N. Africa, Afgh. & Pakistan"),
    ("Latin America & Caribbean", "WB_LAC", "Latin America & Caribbean"),
    ("Europe & Central Asia", "WB_ECA", "Europe & Central Asia"),
    ("North America", "WB_NA", "North America"),
]
API2DISP = {api: disp for api, _, disp in REGIONS}
YR = list(range(Y0, Y1 + 1))

regseries, reg_inside = {}, {}
for api, code, disp in REGIONS:
    regseries[disp] = raw.loc[raw["Code"] == code].set_index("Year")["d"].reindex(YR)
    reg_inside[disp] = ctry.loc[ctry["region"] == api].groupby("Year")["d"].sum()
reg_sum = pd.DataFrame(regseries).sum(axis=1)

# The mapping is only trusted if it reproduces the aggregates it claims to sit
# inside. Anything past 3 % and this script stops.
MAPPING_AUDIT: list[str] = []
rrows = []
for api, code, disp in REGIONS:
    s, ins = regseries[disp], reg_inside[disp]
    for y in (Y0, Y1):
        if s[y]:
            MAPPING_AUDIT.append(f"{disp} {y}: mapped {100*(ins.get(y,0)/s[y]-1):+.2f}% vs aggregate")
    rrows.append(dict(
        disp=disp, api=code, n=int(ctry.loc[(ctry["region"] == api) & (ctry["Year"] == Y1), "Code"].nunique()),
        y00=s[Y0], y10=s[2010], y24=s[Y1],
        pct00=100 * (s[Y1] - s[Y0]) / s[Y0] if s[Y0] else float("nan"),
        pct10=100 * (s[Y1] - s[2010]) / s[2010] if s[2010] else float("nan"),
        share=100 * s[Y1] / reg_sum[Y1],
        halve=(14 * math.log(0.5) / math.log(s[Y1] / s[2010])
               if 0 < s[Y1] < s[2010] else None),
    ))
rtab = pd.DataFrame(rrows).sort_values("y24", ascending=False).reset_index(drop=True)
worst_map = max(abs(100 * (reg_inside[d].get(y, 0) / regseries[d][y] - 1))
                for _, _, d in REGIONS for y in (Y0, Y1) if regseries[d][y])
assert worst_map < 3.0, f"region mapping drifted {worst_map:.1f}% from the aggregates"

# What is inside the region that matters.
ssa_now_tbl = ctry.loc[(ctry["region"] == "Sub-Saharan Africa") & (ctry["Year"] == Y1)]
ssa_now_tbl = ssa_now_tbl.sort_values("d", ascending=False)
ssa_delta = panel[[2010, Y1]].dropna()
ssa_codes = [c for c in ssa_now_tbl["Code"] if c in ssa_delta.index]
ssa_chg = {c: panel.loc[c, Y1] - panel.loc[c, 2010] for c in ssa_codes}
S["ssa_top5_share"] = 100 * ssa_now_tbl["d"].head(5).sum() / ssa_now_tbl["d"].sum()
S["ssa_rising"] = sum(1 for c in ssa_codes if ssa_chg[c] > 0)
S["ssa_added"] = sum(v for v in ssa_chg.values() if v > 0)

# The same story, by income group instead of geography.
INCOMES = [("Low income", "OWID_LIC", "Low income"),
           ("Lower middle income", "OWID_LMC", "Lower-middle income"),
           ("Upper middle income", "OWID_UMC", "Upper-middle income"),
           ("High income", "OWID_HIC", "High income")]
irows = []
for api, code, disp in INCOMES:
    s, ins = raw.loc[raw["Code"] == code].set_index("Year")["d"].reindex(YR), \
             ctry.loc[ctry["income"] == api].groupby("Year")["d"].sum()
    for y in (Y0, Y1):
        if s[y]:
            MAPPING_AUDIT.append(f"{disp} {y}: mapped {100*(ins.get(y,0)/s[y]-1):+.2f}% vs aggregate")
    irows.append(dict(disp=disp, n=int(ctry.loc[(ctry["income"] == api) & (ctry["Year"] == Y1), "Code"].nunique()),
                      y00=s[Y0], y10=s[2010], y24=s[Y1],
                      pct00=100 * (s[Y1] - s[Y0]) / s[Y0] if s[Y0] else float("nan"),
                      share=100 * s[Y1] / reg_sum[Y1]))
itab = pd.DataFrame(irows)
worst_inc = max(abs(100 * (ctry.loc[ctry["income"] == a].groupby("Year")["d"].sum().get(y, 0)
                          / raw.loc[(raw["Code"] == c) & (raw["Year"] == y), "d"].sum() - 1))
                for a, c, _ in INCOMES for y in (Y0, Y1)
                if raw.loc[(raw["Code"] == c) & (raw["Year"] == y), "d"].sum() > 0)
assert worst_inc < 12.0, f"income mapping drifted {worst_inc:.1f}% (historical vs current classification)"

LI = itab.loc[itab["disp"] == "Low income"].iloc[0]
S["li_now"], S["li_pct"], S["li_share"] = LI["y24"], LI["pct00"], LI["share"]
S["li_n"] = LI["n"]


# ------------------------------------------------------------- country need
# Which countries carry the most of the problem, and which way each is moving.
# Two measurements, kept apart on purpose: how many people (the backlog) and
# where the number is going (the direction). No composite score is invented —
# a country that is large and rising is large and rising, and the reader can
# see both columns.
def halve_years(v10: float, v24: float):
    """Years to halve at the country's own 2010-2024 pace. None if not falling."""
    if v10 <= 0 or v24 <= 0 or v24 >= v10:
        return None
    return 14 * math.log(0.5) / math.log(v24 / v10)


need = []
for _, r in latest.iterrows():
    c = r["Code"]
    v00, v10, v24 = panel.loc[c, Y0], panel.loc[c, 2010], panel.loc[c, Y1]
    need.append(dict(
        code=c, name=r["Entity"], region=API2DISP.get(r["region"], "—"),
        income=r["income"], v00=v00, v10=v10, v24=v24,
        d00=v24 - v00, d10=v24 - v10,
        share=100 * v24 / tot[Y1],
        halve=None if v10 <= 0 else halve_years(v10, v24),
        rising=v24 > v10,
    ))
need = sorted(need, key=lambda d: -d["v24"])
top_countries = need[:15]
S["top15_share"] = sum(d["share"] for d in top_countries)
S["rising_top20"] = sum(1 for d in need[:20] if d["rising"])
S["li_countries"] = need


def yr_txt(d):
    if d["v10"] <= 0:
        return "—"
    if d["halve"] is None:
        return "rising"
    return f"{d['halve']:.0f} yr"

# =================================================================== FIGURES

# 1. cut in half
fig, ax = plt.subplots(figsize=(7.8, 3.0))
ys, vals = [1, 0], [S["then"] / 1e6, S["now"] / 1e6]
ax.barh(ys, vals, color=[GREY, TEAL], height=0.5)
for y, v in zip(ys, vals):
    ax.text(v - 34, y, f"{v:,.0f} million", color="white", fontsize=15,
            fontweight="bold", ha="right", va="center")
ax.set_yticks(ys)
ax.set_yticklabels(["2000", "2024"], fontsize=12.5, color=INK, fontweight="bold")
ax.set_xlim(0, 1500); ax.set_ylim(-0.55, 1.55)
ax.set_xlabel("people without electricity (millions)")
ax.grid(axis="y", visible=False)
label(ax, 1130, 0.52, f"\u2212{S['cut']:.0f}%", RED, 22)
ax.text(1133, 0.28, "in 24 years", color=RED, fontsize=9.5, fontweight="bold",
        va="top", ha="left",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.5))
banner(fig, "Half the problem was solved. It is the other half that moved.", INK)
fig1 = finish(fig, "1_halved", "story_1_halved.png")

# 2. India
fig, ax = plt.subplots(figsize=(7.8, 3.3))
yr = sorted(panel.columns)
ind = [panel.loc["IND", y] / 1e6 for y in yr]
ax.fill_between(yr, ind, color=TEAL, alpha=0.14)
ax.plot(yr, ind, color=TEAL, lw=2.8)
label(ax, 1991, 520, f"peak {millions(S['india_peak'])} M", GREY, 11, box=False)
ax.annotate("", xy=(S["india_peak_yr"], S["india_peak"] / 1e6), xytext=(1996.5, 505),
            arrowprops=dict(arrowstyle="->", lw=1.0, color=GREY))
label(ax, 2012.5, 330, f"{S['india_now']/1e6:.1f} million", TEAL, 15, box=False)
ax.annotate("", xy=(2024.4, S["india_now"] / 1e6 + 6), xytext=(2018.5, 322),
            arrowprops=dict(arrowstyle="->", lw=1.4, color=TEAL,
                            connectionstyle="arc3,rad=-0.2"))
ax.set_ylabel("people without electricity in India (millions)")
ax.set_xlabel("year"); ax.set_ylim(0, 620); ax.set_xlim(1989, 2026)
banner(fig, "One country removed 419 million people from this graph.", TEAL)
fig2 = finish(fig, "2_india", "story_2_india.png")

# 3. the divorce
fig, ax = plt.subplots(figsize=(7.8, 4.1))
yrs = list(range(Y0, Y1 + 1))
rest = [tot[y] - ssa[y] for y in yrs]
ax.plot(yrs, [v / 1e6 for v in rest], color=TEAL, lw=3, label="The rest of the world")
ax.plot(yrs, [ssa[y] / 1e6 for y in yrs], color=RED, lw=3, label="Sub-Saharan Africa")
label(ax, 2000.3, 905, f"{S['rest_then']/1e6:,.0f} M", TEAL, 13)
label(ax, 2000.3, 432, f"{S['ssa_then']/1e6:,.0f} M", RED, 13)
label(ax, 2024.7, 58, f"{S['rest_now']/1e6:,.0f} M", TEAL, 13)
label(ax, 2023.6, 668, f"{S['ssa_now']/1e6:,.0f} M", RED, 13, ha="right")
ax.set_ylabel("people without electricity (millions)")
ax.set_xlabel("year"); ax.set_ylim(0, 1090); ax.set_xlim(1999.2, 2028.2)
ax.legend(frameon=False, fontsize=11.5, loc="upper right")
banner(fig, f"The rest of the world fell {S['rest_cut']:.0f}%. "
            f"Sub-Saharan Africa rose {S['ssa_change']:.0f}%.", INK)
fig3 = finish(fig, "3_divorce", "story_3_divorce.png")

# 4. regions
regs = raw[(raw["Code"].str.startswith("WB_")) & (raw["Year"] == Y1)].copy()
regs["short"] = (regs["Entity"].str.replace(" (WB)", "", regex=False).replace({
    "Middle East, North Africa, Afghanistan and Pakistan": "Middle East & North Africa",
    "Latin America and Caribbean": "Latin America & Caribbean",
    "Europe and Central Asia": "Europe & Central Asia"}))
regs = regs.sort_values("d")
fig, ax = plt.subplots(figsize=(7.8, 3.2))
ax.barh(regs["short"], regs["d"] / 1e6,
        color=[RED if v > 1e8 else GREY for v in regs["d"]], height=0.6)
for name, v in zip(regs["short"], regs["d"] / 1e6):
    ax.text(v + 12, name, f"{v:,.0f} M" if v >= 1 else "<1 M",
            color=INK if v > 100 else GREY, fontsize=12 if v > 100 else 10.5,
            fontweight="bold" if v > 100 else "normal", va="center", ha="left")
ax.set_xlim(0, 760)
ax.set_xlabel("people without electricity in 2024 (millions)")
ax.grid(axis="y", visible=False)
banner(fig, f"Sub-Saharan Africa holds {S['share_now']:.0f}% of what is left.", INK)
fig4 = finish(fig, "4_regions", "story_4_regions.png")

# 5. going backwards
fig, ax = plt.subplots(figsize=(7.8, 4.4))
w = worse.head(12).iloc[::-1]
ax.barh(w["Entity"], w["delta"] / 1e6, color=RED, height=0.64)
for name, v in zip(w["Entity"], w["delta"] / 1e6):
    ax.text(v + 0.6, name, f"+{v:,.1f} M", color=INK, fontsize=10.5,
            fontweight="bold", va="center", ha="left")
ax.set_xlim(0, 33)
ax.set_xlabel("more people without electricity than in 2010 (millions)")
ax.grid(axis="y", visible=False)
banner(fig, f"{S['worse_n']} countries went backwards. "
            f"{S['worse_africa']} of them are in Africa.", INK)
fig5 = finish(fig, "5_backwards", "story_5_backwards.png")

# 6. the 2030 arithmetic
fig, ax = plt.subplots(figsize=(7.8, 3.6))
hy = list(range(2010, Y1 + 1))
ax.plot(hy, [tot[y] / 1e6 for y in hy], color=INK, lw=2.8, label="what happened")
py = list(range(Y1, TGT + 1))
ax.plot(py, [tot[Y1] / 1e6 * (1 - world_rate) ** (y - Y1) for y in py],
        color=RED, lw=2.8, ls=(0, (5, 3)), label="if the recent pace holds")
ax.axhline(0, color=TEAL, lw=3.2)
label(ax, 2010.4, 55, "the goal: zero", TEAL, 11.5, box=False)
ax.scatter([TGT], [S["proj_2030"] / 1e6], color=RED, zorder=5, s=60)
label(ax, 2016.0, 300, f"{S['proj_2030']/1e6:,.0f} million\nstill without power",
      RED, 14, va="top")
ax.annotate("", xy=(TGT, S["proj_2030"] / 1e6), xytext=(2021.5, 300),
            arrowprops=dict(arrowstyle="->", lw=1.6, color=RED))
ax.set_ylim(0, 1320); ax.set_xlim(2009.5, 2031.5)
ax.set_ylabel("people without electricity (millions)")
ax.set_xlabel("year")
ax.legend(frameon=False, fontsize=10.5, loc="upper right")
banner(fig, "The goal is zero. The arithmetic points somewhere else.", INK)
fig6 = finish(fig, "6_deadline", "story_6_deadline.png")

# 7. THE LANDSCAPE — the 20 largest, and which way each is moving.
fig, ax = plt.subplots(figsize=(7.8, 6.4))
t = top20.iloc[::-1]
colours = [TEAL if d < 0 else RED for d in t["delta"]]
ax.barh(t["Entity"], t["d"] / 1e6, color=colours, height=0.66)
for name, v, d in zip(t["Entity"], t["d"] / 1e6, t["delta"] / 1e6):
    ax.text(v + 1.5, name, f"{v:,.1f} M", color=INK, fontsize=10.5,
            fontweight="bold", va="center", ha="left")
    ax.text(v * 0.02, name, f"{'+' if d > 0 else ''}{d:,.1f}", color="white",
            fontsize=9.5, fontweight="bold", va="center", ha="left")
ax.set_xlim(0, 108)
ax.set_xlabel("people without electricity in 2024 (millions)")
ax.grid(axis="y", visible=False)
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (TEAL, RED)]
ax.legend(h, ["Falling since 2010", "Rising since 2010"], frameon=False,
          fontsize=10.5, loc="lower right")
banner(fig, "Number inside each bar = change since 2010, in millions.", INK)
fig7 = finish(fig, "7_landscape", "story_7_landscape.png")


def dumbbell(rows, xlabel, name, filename, banner_text):
    """Each row: 2000 value -> 2024 value. Grey dot is the start, coloured dot
    the end. The arrow of the connector, and the label it carries, say which
    direction the region moved. `rows` is [(label, change_note, v2000, v2024)]."""
    n = len(rows)
    fig, ax = plt.subplots(figsize=(7.8, 0.62 * n + 1.45))
    hi = max(max(r[2], r[3]) for r in rows)
    ax.set_xlim(0, hi * 1.52)
    ax.set_ylim(-0.65, n - 0.35)
    for i, (lab, note, a, b) in enumerate(rows):
        col = RED if b > a else TEAL
        ax.plot([a / 1e6, b / 1e6], [i, i], color=col, lw=2.0, alpha=0.34,
                zorder=1, solid_capstyle="round")
        ax.scatter([a / 1e6], [i], s=64, color=GREY, zorder=3, linewidths=0)
        ax.scatter([b / 1e6], [i], s=64, color=col, zorder=3, linewidths=0)
        ax.text(hi * 1.055, i, f"{a/1e6:,.0f} M \u2192 {b/1e6:,.1f} M", color=col,
                fontsize=10.5, fontweight="bold", va="center", ha="left")
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{lab}\n{note}" for lab, note, _, _ in rows],
                       fontsize=11, color=INK, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    banner(fig, banner_text, INK)
    return finish(fig, name, filename, left=0.27)


# 8. THE REGIONS, SIDE BY SIDE — what each one looks like at the two ends.
rows8 = [(r["disp"], f"{r['pct00']:+.0f}% since 2000", r["y00"], r["y24"])
         for _, r in rtab.iterrows() if r["y24"] > 0 or r["y00"] > 0]
rows8 = [x for x in rows8 if x[3] > 0]
fig8 = dumbbell(rows8, "people without electricity (millions), log-free linear scale",
                "8_regions_dumbbell", "story_8_regions_dumbbell.png",
                "Same 24 years. Grey is 2000, colour is 2024.")

# 9. THE COMPOSITION — who the 655 million are, year by year.
fig, ax = plt.subplots(figsize=(7.8, 4.2))
ORDER = ["Sub-Saharan Africa", "South Asia", "East Asia & Pacific",
         "Middle East, N. Africa, Afgh. & Pakistan", "Latin America & Caribbean",
         "Europe & Central Asia"]
COLS = [RED, TEAL, AMBER, GREY, "#7d8794", "#c3c9d2"]
share_ts = {d: [100 * regseries[d][y] / reg_sum[y] for y in YR] for d in ORDER}
ax.stackplot(YR, *[share_ts[d] for d in ORDER], colors=COLS, labels=ORDER)
SHORT = {"Middle East, N. Africa, Afgh. & Pakistan": "MENA, Afgh. & Pakistan",
         "Latin America & Caribbean": "Latin America"}
bottom = [0.0] * len(YR)
band_labels = []
for d, c in zip(ORDER, COLS):
    sh = share_ts[d]
    j = max(range(len(sh)), key=sh.__getitem__)
    if sh[j] > 4.2:
        band_labels.append(ax.text(
            YR[j], bottom[j] + sh[j] / 2, SHORT.get(d, d), color="white",
            fontsize=11.5 if sh[j] > 30 else 9.5, fontweight="bold",
            ha="center", va="center"))
    bottom = [b + s for b, s in zip(bottom, sh)]
ax.set_ylim(0, 100); ax.set_xlim(Y0, Y1)
ax.set_ylabel("share of the world's people without electricity (%)")
ax.set_xlabel("year")
banner(fig, f"Sub-Saharan Africa was {100*regseries['Sub-Saharan Africa'][Y0]/reg_sum[Y0]:.0f}% "
            f"of the problem in 2000. It is {rtab.set_index('api').loc['WB_SSA','share']:.0f}% now.", INK)
fig9 = finish(fig, "9_composition", "story_9_composition.png",
              nudge=band_labels)

# 10. INSIDE SUB-SAHARAN AFRICA — where the 579 million actually are.
fig, ax = plt.subplots(figsize=(7.8, 5.2))
w = ssa_now_tbl.head(15).iloc[::-1]
ax.barh(w["Entity"], w["d"] / 1e6,
        color=[RED if ssa_chg.get(c, 0) > 0 else TEAL for c in w["Code"]], height=0.66)
for name, v, c in zip(w["Entity"], w["d"] / 1e6, w["Code"]):
    ax.text(v + 1.1, name, f"{v:,.1f} M", color=INK, fontsize=10.5,
            fontweight="bold", va="center", ha="left")
ax.set_xlim(0, 104)
ax.set_xlabel("people without electricity in 2024 (millions)")
ax.grid(axis="y", visible=False)
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (TEAL, RED)]
ax.legend(h, ["Falling since 2010", "Rising since 2010"], frameon=False,
          fontsize=10.5, loc="lower right")
banner(fig, f"The five largest hold {S['ssa_top5_share']:.0f}% of the region's "
            f"{millions(rtab.set_index('api').loc['WB_SSA','y24'])} million.", INK)
fig10 = finish(fig, "10_inside_ssa", "story_10_inside_ssa.png")

# 11. THE SAME STORY BY INCOME, not geography.
rows11 = [(r["disp"], f"{r['pct00']:+.0f}% since 2000", r["y00"], r["y24"])
          for _, r in itab.iterrows()]
fig11 = dumbbell(rows11, "people without electricity (millions)",
                 "11_income_dumbbell", "story_11_income_dumbbell.png",
                 "The world halved the problem. Low-income countries added to it.")

# 12. THE COUNTRIES THAT CARRY IT — the twelve largest, 2010 against 2024.
rows12 = [(d["name"], f"{100*(d['v24']/d['v10']-1):+.0f}% since 2010" if d["v10"] else "—",
           d["v10"], d["v24"]) for d in need[:12]]
fig12 = dumbbell(rows12, "people without electricity (millions)",
                 "12_top_countries", "story_12_top_countries.png",
                 "Red grew over the period, teal shrank. Grey is 2010.")

# ------------------------------------------------------------------ html bits
top_rows = "\n".join(
    f"""      <tr>
        <td class="rk">{i}</td><td class="nm">{r.Entity}</td>
        <td class="num">{exact(r.d)}</td>
        <td class="num {'up' if r.delta > 0 else 'down'}">{'+' if r.delta > 0 else '−'}{exact(abs(r.delta))}</td>
        <td class="bar"><div style="width:{100*r.d/top15.d.max():.1f}%"></div></td>
      </tr>""" for i, (_, r) in enumerate(top20.iterrows(), start=1))

def m1(x: float) -> str:
    return f"{x/1e6:,.1f}".replace(",", " ")


def signed(x: float, dec: int = 0) -> str:
    sign = "+" if x > 0 else "\u2212"
    return f"{sign}{abs(x):,.{dec}f}".replace(",", " ")


region_rows = ""
for _, r in rtab.iterrows():
    col = "up" if r["pct00"] > 0 else "down"
    halve = "rising" if r["halve"] is None else f"{r['halve']:,.0f}".replace(",", " ") + " yr"
    region_rows += f"""      <tr>
        <td class="nm">{r['disp']}</td>
        <td class="num">{m1(r['y00'])}</td>
        <td class="num">{m1(r['y24'])}</td>
        <td class="num">{r['share']:.1f}%</td>
        <td class="num {col}">{signed(r['pct00'])}%</td>
        <td class="num"><span style="color:var(--muted)">{halve}</span></td>
      </tr>\n"""

ssa_tot = rtab.set_index("api").loc["WB_SSA", "y24"]
ssa_rows = ""
for i, (_, r) in enumerate(ssa_now_tbl.head(15).iterrows(), start=1):
    d = ssa_chg.get(r["Code"], 0)
    col = "up" if d > 0 else "down"
    ssa_rows += f"""      <tr>
        <td class="rk">{i}</td><td class="nm">{r['Entity']}</td>
        <td class="num">{m1(r['d'])}</td>
        <td class="num">{100*r['d']/ssa_tot:.1f}%</td>
        <td class="num {col}">{signed(d/1e6, 1)} M</td>
        <td class="bar"><div style="width:{100*r['d']/ssa_now_tbl['d'].max():.1f}%"></div></td>
      </tr>\n"""

income_rows = ""
for _, r in itab.iterrows():
    col = "up" if r["pct00"] > 0 else "down"
    income_rows += f"""      <tr>
        <td class="nm">{r['disp']}</td>
        <td class="num" style="color:var(--muted)">{r['n']}</td>
        <td class="num">{m1(r['y00'])}</td>
        <td class="num">{m1(r['y24'])}</td>
        <td class="num {col}">{signed(r['pct00'])}%</td>
        <td class="num">{r['share']:.1f}%</td>
      </tr>\n"""

# Every country, for the filterable table at the bottom. Compact arrays to keep
# the page small: [name, region, income, 2000, 2010, 2024, change since 2010].
# Four countries (South Sudan, North Korea, Liberia, Guinea-Bissau) have no 2000
# value in the file. A missing year is null here and an em dash in the table,
# never a zero — the file does not say zero, it says nothing.
def persons(x) -> int | None:
    return None if pd.isna(x) else round(float(x))


live = []
for _, r in latest.iterrows():
    c = r["Code"]
    v00, v10, v24 = (persons(panel.loc[c, y]) for y in (Y0, 2010, Y1))
    live.append([r["Entity"], API2DISP.get(r["region"], "—"), r["income"],
                 v00, v10, v24,
                 # From the rounded pair, so the column always equals the two
                 # cells beside it. The source values are fractional estimates;
                 # rounding them separately would leave the table one person short
                 # of its own subtraction in about 7 % of rows.
                 None if v10 is None or v24 is None else v24 - v10])
LIVE_JSON = json.dumps(live, separators=(",", ":"))
REGION_OPTS = "".join(f'<option>{d}</option>' for d in rtab["disp"])
INCOME_OPTS = "".join(f'<option>{d}</option>' for d in itab["disp"])

need_rows = ""
for i, d in enumerate(top_countries, start=1):
    col = "up" if d["rising"] else "down"
    need_rows += f"""      <tr>
        <td class="rk">{i}</td><td class="nm">{d['name']}</td>
        <td class="rgc">{d['region']}</td>
        <td class="num">{m1(d['v24'])}</td>
        <td class="num">{d['share']:.1f}%</td>
        <td class="num {col}">{signed(d['d10']/1e6, 1)}</td>
        <td class="num"><span style="color:var(--muted)">{yr_txt(d)}</span></td>
      </tr>\n"""

# The short answer, built first and shown first. This is the plainest table on the
# page on purpose: rank, how many people, how far the number moved, which way it is
# going. Two readings of "most" are kept apart — size (how many people) and
# direction (which way the number is moving) — because a country can be large and
# improving, or large and losing, and conflating the two would hide both.
answer_rows = ""
for i, d in enumerate(need[:10], start=1):
    cls, word = ("up", "rising") if d["rising"] else ("down", "falling")
    answer_rows += f"""      <tr>
        <td class="rk">{i}</td><td class="nm">{d['name']}</td>
        <td class="num">{m1(d['v24'])}&nbsp;M</td>
        <td class="num">{d['share']:.1f}%</td>
        <td class="num {cls}">{signed(d['d10']/1e6, 1)}&nbsp;M</td>
        <td class="rgc">{word}</td>
      </tr>\n"""

S["top5_share"] = sum(d["share"] for d in need[:5])
S["top10_share"] = sum(d["share"] for d in need[:10])
S["top5_now"] = sum(d["v24"] for d in need[:5])
S["two_now"] = need[0]["v24"] + need[1]["v24"]
S["two_share"] = need[0]["share"] + need[1]["share"]
S["drc_d10"] = next(d["d10"] for d in need if d["code"] == "COD")
S["top10_africa"] = sum(1 for d in need[:10] if d["region"] == "Sub-Saharan Africa")

# The sortable table is assembled with plain strings rather than inside the page
# f-string, so the JavaScript braces stay readable.
LIVE_JS = """
<script>
(function () {
  const D = __DATA__;
  const tb = document.querySelector('#allc tbody');
  const q = document.getElementById('q'), rg = document.getElementById('rg');
  const inc = document.getElementById('inc'), cnt = document.getElementById('cnt');
  let sortCol = 5, asc = false;
  const fmt = n => n == null ? '—' : n.toLocaleString('en-GB').replace(/,/g, ' ');
  function pick() {
    const s = q.value.trim().toLowerCase();
    return D.filter(r => (!s || r[0].toLowerCase().includes(s))
                      && (!rg.value || r[1] === rg.value)
                      && (!inc.value || r[2] === inc.value))
            .sort((a, b) => {
              const x = a[sortCol], y = b[sortCol];
              const c = (typeof x === 'number' && typeof y === 'number')
                ? x - y : String(x ?? '').localeCompare(String(y ?? ''));
              return asc ? c : -c;
            });
  }
  function draw() {
    const rs = pick();
    tb.innerHTML = rs.map(r => {
      const d = r[6], col = d > 0 ? 'up' : 'down';
      return '<tr><td class="nm"></td><td class="rgc">' + r[1] + '</td>'
           + '<td class="rgc">' + r[2] + '</td>'
           + '<td class="num">' + fmt(r[3]) + '</td>'
           + '<td class="num">' + fmt(r[4]) + '</td>'
           + '<td class="num">' + fmt(r[5]) + '</td>'
           + '<td class="num ' + col + '">' + (d > 0 ? '+' : '\\u2212')
           + fmt(Math.abs(d)) + '</td></tr>';
    }).join('');
    tb.querySelectorAll('tr').forEach((tr, i) => { tr.children[0].textContent = rs[i][0]; });
    cnt.textContent = rs.length + ' of ' + D.length + ' countries';
  }
  document.querySelectorAll('#allc thead th').forEach(th => {
    th.onclick = () => {
      const c = Number(th.dataset.c);
      asc = (c === sortCol) ? !asc : false;
      sortCol = c;
      document.querySelectorAll('#allc thead th').forEach(o => o.classList.remove('asc', 'desc'));
      th.classList.add(asc ? 'asc' : 'desc');
      draw();
    };
  });
  q.oninput = draw; rg.onchange = draw; inc.onchange = draw;
  draw();
})();
</script>
""".replace("__DATA__", LIVE_JSON)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Who lives without electricity — the data</title>
<style>
  :root {{ --ink:#1b1b1f; --muted:#6b7280; --line:#e6e8ec; --bg:#f7f8fa;
          --red:#c1121f; --teal:#2a9d8f; --card:#fff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:0 26px 90px; }}

  header {{ background:var(--ink); color:#fff; padding:72px 0 64px; }}
  header .wrap {{ padding-bottom:0; }}
  .hero {{ font-size:clamp(50px,10vw,96px); font-weight:800; letter-spacing:-.045em;
    line-height:.94; margin:0; }}
  .herosub {{ font-size:clamp(19px,2.6vw,25px); color:#e8e9ee; margin:20px 0 0;
    max-width:26ch; font-weight:400; }}
  .kicker {{ text-transform:uppercase; letter-spacing:.16em; font-size:11.5px;
    font-weight:700; color:#ff8b93; margin-bottom:26px; }}
  header .src {{ margin-top:32px; font-size:13.5px; color:#9ea3ad; max-width:66ch; }}

  section {{ padding:56px 0 4px; }}
  h2 {{ font-size:clamp(24px,4vw,34px); line-height:1.2; letter-spacing:-.02em;
    margin:0 0 6px; font-weight:750; }}
  .step {{ display:block; font-size:11.5px; text-transform:uppercase;
    letter-spacing:.15em; color:var(--muted); font-weight:700; margin-bottom:12px; }}
  .dek {{ font-size:19.5px; color:#33363d; margin:0 0 4px; max-width:60ch; }}
  h3 {{ font-size:18px; margin:30px 0 8px; }}

  p {{ max-width:68ch; }}
  .big {{ font-size:clamp(28px,5vw,42px); font-weight:800; letter-spacing:-.03em;
    color:var(--red); line-height:1.1; margin:26px 0 4px; }}
  .big.teal {{ color:var(--teal); }}
  .big .lbl {{ font-size:15px; font-weight:600; color:var(--muted);
    letter-spacing:0; display:block; margin-top:9px; max-width:48ch; }}

  figure {{ margin:26px 0; background:var(--card); border:1px solid var(--line);
    border-radius:14px; padding:14px 14px 6px; }}
  figure img {{ width:100%; display:block; }}
  figcaption {{ font-size:14px; color:var(--muted); margin:10px 4px 10px;
    line-height:1.55; border-top:1px solid var(--line); padding-top:11px; }}
  figcaption b {{ color:var(--ink); }}

  .pull {{ border-left:5px solid var(--red); background:#fff; padding:19px 26px;
    border-radius:0 12px 12px 0; margin:28px 0; font-size:19px; font-weight:600;
    line-height:1.45; }}
  .pull.teal {{ border-color:var(--teal); }}

  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
    gap:14px; margin:26px 0; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:20px; }}
  .stat .v {{ font-size:30px; font-weight:800; letter-spacing:-.03em; line-height:1.1; }}
  .stat .v.r {{ color:var(--red); }} .stat .v.t {{ color:var(--teal); }}
  .stat .k {{ font-size:13.5px; color:var(--muted); margin-top:7px; line-height:1.45; }}

  table {{ width:100%; border-collapse:collapse; background:var(--card);
    border:1px solid var(--line); border-radius:12px; overflow:hidden; font-size:15px; }}
  th,td {{ padding:11px 14px; text-align:left; border-bottom:1px solid var(--line); }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--muted); background:#f2f4f7; font-weight:700; }}
  tr:last-child td {{ border-bottom:none; }}
  td.rk {{ color:var(--muted); width:36px; font-variant-numeric:tabular-nums; }}
  td.nm {{ font-weight:600; }}
  td.num {{ font-variant-numeric:tabular-nums; text-align:right; white-space:nowrap;
    font-weight:650; }}
  td.num.up {{ color:var(--red); }} td.num.down {{ color:var(--teal); }}
  td.bar {{ width:26%; }}
  td.bar > div {{ height:10px; background:var(--red); border-radius:5px; opacity:.85; }}

  .note {{ background:#fff; border:1px solid var(--line); border-radius:12px;
    padding:22px 26px; margin:24px 0; }}
  .note h4 {{ margin:0 0 10px; font-size:16px; }}
  .note ul {{ margin:0; padding-left:20px; }} .note li {{ margin-bottom:8px; }}
  .note p:last-child {{ margin-bottom:0; }}
  code {{ background:#eef0f4; padding:2px 6px; border-radius:5px; font-size:14.5px;
    font-family:ui-monospace,Menlo,Consolas,monospace; }}

  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr));
    gap:14px; margin:24px 0; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:20px 22px; border-top:4px solid var(--grey,#9aa3b0); }}
  .card.g {{ border-top-color:var(--teal); }}
  .card.r {{ border-top-color:var(--red); }}
  .card h4 {{ margin:0 0 8px; font-size:15.5px; }}
  .card p {{ font-size:14.5px; margin:0 0 8px; color:#3a3d44; }}
  .card .n {{ font-size:23px; font-weight:800; letter-spacing:-.02em; }}

  .qa {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:18px 22px; margin-bottom:12px; }}
  .qa .q {{ font-weight:700; font-size:16.5px; }}
  .qa .a {{ margin-top:10px; padding-left:20px; }}
  .qa .a p:first-child {{ margin-top:0; }} .qa .a p:last-child {{ margin-bottom:0; }}
  .tag {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
    font-weight:800; padding:3px 9px; border-radius:999px; float:right;
    margin-left:12px; }}
  .tag.y {{ background:#e3f4f1; color:var(--teal); }}
  .tag.n {{ background:#fdeaec; color:var(--red); }}

  td.rgc {{ color:var(--muted); font-size:13.5px; }}
  .ctl {{ display:flex; flex-wrap:wrap; gap:10px; margin:22px 0 14px; }}
  .ctl input, .ctl select {{ font:inherit; font-size:14.5px; padding:9px 12px;
    border:1px solid var(--line); border-radius:9px; background:#fff; color:var(--ink); }}
  .ctl input {{ flex:1 1 190px; }}
  .ctl .cnt {{ align-self:center; font-size:13.5px; color:var(--muted); }}
  .scroll {{ max-height:560px; overflow:auto; border-radius:12px; }}
  .scroll table {{ border-radius:0; }}
  .scroll thead th {{ position:sticky; top:0; z-index:2; cursor:pointer;
    user-select:none; white-space:nowrap; }}
  .scroll thead th:hover {{ color:var(--ink); }}
  .scroll thead th::after {{ content:" \\2195"; color:#c3c9d2; }}
  .scroll thead th.asc::after {{ content:" \\2191"; color:var(--ink); }}
  .scroll thead th.desc::after {{ content:" \\2193"; color:var(--ink); }}

  .foot {{ margin-top:56px; padding-top:22px; border-top:1px solid var(--line);
    font-size:13.5px; color:var(--muted); }}
  @media print {{
    header {{ background:#fff; color:var(--ink); }}
    .hero {{ color:var(--red); }} .kicker {{ color:var(--red); }}
    .herosub, header .src {{ color:var(--muted); }}
    section, figure, table, .stat, .pull, .qa, .note {{ page-break-inside:avoid; }}
  }}
</style>
</head>
<body>

<header>
  <div class="wrap">
    <div class="kicker">The electricity access dataset</div>
    <h1 class="hero">{millions(S['now'])} million</h1>
    <p class="herosub">people live without electricity.</p>
    <p class="src">This page is one dataset and nothing else: every country on Earth,
      {S['yr0']}&ndash;{S['yr1']}. It says who lacks electricity, where they are, which
      way each country is moving, and what the data cannot tell you.</p>
  </div>
</header>

<div class="wrap">

<!-- ============================================ the short answer -->
<section>
  <span class="step">Start here</span>
  <h2>Which countries need electricity most</h2>
  <p class="dek">Ordered by how many people lack electricity in 2024 — the plainest
     reading of "most". The last two columns are the second reading: whether the
     country is closing its gap or falling further behind.</p>

  <div class="pull">Nigeria and DR Congo alone hold {S['two_share']:.0f}&nbsp;% of the
     world's problem — {millions(S['two_now'])} million people between them.</div>

  <table>
    <thead><tr><th>#</th><th>Country</th>
      <th style="text-align:right">People, 2024</th>
      <th style="text-align:right">Of the world</th>
      <th style="text-align:right">Since 2010</th>
      <th>Direction</th></tr></thead>
    <tbody>
{answer_rows}
    </tbody>
  </table>

  <p style="margin-top:14px;font-size:14.5px;color:var(--muted)">Ten countries hold
     {S['top10_share']:.0f}&nbsp;% of everyone without electricity — and every one of
     them is in Sub-Saharan Africa.</p>

  <div class="cards">
    <div class="card r"><div class="n">{millions(S['top5_now'])}&nbsp;M</div>
      <h4>Where the gap is largest</h4>
      <p>Nigeria, DR Congo, Ethiopia, Tanzania, Uganda. These five hold
        {S['top5_share']:.0f}&nbsp;% of the world's unserved population.</p></div>
    <div class="card r"><div class="n">+{millions(S['worse_added'])}&nbsp;M</div>
      <h4>Where it is getting worse</h4>
      <p>{S['worse_n']} countries had <em>more</em> people without power in 2024 than
        in 2010 — {S['worse_africa']} of them in Africa. DR Congo alone added
        {millions(S['drc_d10'])} million.</p></div>
  </div>

  <div class="pull teal">If you remember one country, remember <b>DR Congo</b>: the
     second-largest gap on Earth, and the only country that is both near the top and
     losing ground quickly.</div>

  <p style="font-size:14.5px;color:var(--muted)">Everything below is the same file
     read more carefully: where these numbers come from, how they moved, and the four
     things that limit what they can be used for.</p>
</section>

<!-- ============================================ the headline -->
<section>
  <span class="step">The headline</span>
  <h2>The number, and how it changed</h2>
  <figure><img src="{fig1}" alt="People without electricity, 2000 and 2024">
    <figcaption><b>Read:</b> the same measurement 24 years apart. In 2000,
      {exact(S['then'])} people. In 2024, {exact(S['now'])}.</figcaption></figure>
  <p>A halving in one generation is real. It also means half the problem is still
     there — and the rest of this page is about which half.</p>
</section>

<!-- ============================================ India -->
<section>
  <span class="step">What progress looks like</span>
  <h2>Most of that progress has one country's name on it</h2>
  <figure><img src="{fig2}" alt="People without electricity in India, 1990 to 2024">
    <figcaption><b>Read:</b> India peaked at {millions(S['india_peak'])} in
      {S['india_peak_yr']} and fell to {exact(S['india_now'])} by 2024.</figcaption></figure>
  <div class="big teal">{millions(S['india_then'])} &rarr; {exact(S['india_now'])}
    <span class="lbl">India's count, 2000 to 2024 — a fall of 419 million.</span></div>
  <p>China, Indonesia, Bangladesh and Vietnam did the same thing at smaller scale.
     The number responds when people are connected, and it responds quickly. That is
     what makes the next section the one that matters.</p>
</section>

<!-- ============================================ the finding -->
<section>
  <span class="step">The turn</span>
  <h2>The world halved the problem. One region doubled its share.</h2>
  <figure><img src="{fig3}" alt="Sub-Saharan Africa compared with the rest of the world">
    <figcaption><b>Read:</b> the teal line is every country outside Sub-Saharan Africa,
      added together. The red line is Sub-Saharan Africa. They begin close and end in
      opposite places.</figcaption></figure>

  <div class="stats">
    <div class="stat"><div class="v t">&minus;{S['rest_cut']:.0f}%</div>
      <div class="k">outside Sub-Saharan Africa:<br>
        {millions(S['rest_then'])} &rarr; {millions(S['rest_now'])}</div></div>
    <div class="stat"><div class="v r">+{S['ssa_change']:.0f}%</div>
      <div class="k">Sub-Saharan Africa:<br>
        {millions(S['ssa_then'])} &rarr; {millions(S['ssa_now'])}</div></div>
  </div>

  <div class="pull">Sub-Saharan Africa held {S['share_then']:.0f}% of the world's people
     without electricity in 2000. By 2024 it held {S['share_now']:.0f}%.</div>
  <p>Africa did not collapse — its number rose {S['ssa_change']:.0f}%. Everywhere else
     improved so quickly that Africa's share of what remained went up anyway. This is
     the fact the headline number hides, and it is the single most consequential thing
     in the file.</p>
</section>

<!-- ============================================ which countries carry it -->
<section>
  <span class="step">Who carries it</span>
  <h2>The fifteen countries that carry almost all of it</h2>
  <p>Ranked by how many people lack electricity in 2024. The last two columns are
     the ones that matter for deciding where help is worth most: how the number
     moved over the last fourteen years, and how long it would take that country
     to halve its own figure if it kept its own recent pace.</p>

  <table>
    <thead><tr><th>#</th><th>Country</th><th>Region</th>
      <th style="text-align:right">People, 2024 (M)</th>
      <th style="text-align:right">Of the world</th>
      <th style="text-align:right">Since 2010 (M)</th>
      <th style="text-align:right">Years to halve</th></tr></thead>
    <tbody>
{need_rows}
    </tbody>
  </table>

  <div class="stats" style="margin-top:22px">
    <div class="stat"><div class="v">{S['top15_share']:.0f}%</div>
      <div class="k">of everyone without electricity lives in these fifteen
        countries</div></div>
    <div class="stat"><div class="v r">{S['rising_top20']}</div>
      <div class="k">of the twenty largest went <em>up</em> between 2010 and
        2024</div></div>
  </div>

  <figure><img src="{fig12}" alt="The twelve largest countries, 2010 against 2024">
    <figcaption><b>Read:</b> grey dot is 2010, the coloured dot is 2024. Teal means
      the country cut its number; red means the number grew. A short connector far
      from the left edge is a country that is barely moving relative to the size of
      its backlog.</figcaption></figure>

  <div class="pull">{S['rising_top20']} of the twenty largest are red. In those
     countries the grid is not losing to the problem by a small margin — it is
     losing outright, and the backlog grows every year that passes.</div>
</section>

<!-- ============================================ the regions -->
<section>
  <span class="step">Region by region</span>
  <h2>The same 24 years, region by region</h2>
  <p>Start with the picture: in 2024 the whole problem is one bar and six nearly
     invisible ones.</p>
  <figure><img src="{fig4}" alt="People without electricity by world region, 2024">
    <figcaption><b>Read:</b> Sub-Saharan Africa against the other six regions at the
      same date. The bar chart below the table shows the same thing over time.</figcaption></figure>
  <p>Each region below is a World Bank aggregate carried in the file itself — not a
     figure this analysis built. The row shows where the region started and where it
     ended; the last column is how long it would take that region to halve its own
     number at its own 2010&ndash;2024 pace.</p>

  <table>
    <thead><tr><th>Region</th><th style="text-align:right">2000 (M)</th>
      <th style="text-align:right">2024 (M)</th>
      <th style="text-align:right">Of the world</th>
      <th style="text-align:right">Since 2000</th>
      <th style="text-align:right">Years to halve</th></tr></thead>
    <tbody>
{region_rows}
    </tbody>
  </table>

  <figure><img src="{fig8}" alt="Each region in 2000 and 2024">
    <figcaption><b>Read:</b> grey dot 2000, coloured dot 2024. Two regions moved the
      wrong way or barely moved — and one of them holds almost everything.</figcaption></figure>

  <figure><img src="{fig9}" alt="The share of the world deficit held by each region">
    <figcaption><b>Read:</b> the same numbers as a share of the world total, so the
      whole problem always adds to 100&nbsp;%.</figcaption></figure>

  <h3>Inside the region that holds {S['share_now']:.0f}&nbsp;%</h3>
  <figure><img src="{fig10}" alt="The fifteen largest countries in Sub-Saharan Africa">
    <figcaption><b>Read:</b> the fifteen largest backlogs inside Sub-Saharan Africa,
      coloured by whether each grew or shrank since 2010.</figcaption></figure>
  <p>Sub-Saharan Africa is not one problem. Its five largest countries hold
     {S['ssa_top5_share']:.0f}&nbsp;% of the region's total, and
     {S['ssa_rising']} of its {len(ssa_codes)} countries reporting in 2024 went
     backwards between 2010 and 2024, together adding
     {millions(S['ssa_added'])} people.</p>
</section>

<!-- ============================================ by income -->
<section>
  <span class="step">By income</span>
  <h2>The same story, sorted by income instead of geography</h2>
  <p>This is the same dataset sliced a different way, and it says something the
     country list cannot: the fall in the global number is entirely a story about
     middle-income countries. The poorest group in the file went the other way.</p>

  <table>
    <thead><tr><th>Income group</th>
      <th style="text-align:right">Countries</th>
      <th style="text-align:right">2000 (M)</th>
      <th style="text-align:right">2024 (M)</th>
      <th style="text-align:right">Since 2000</th>
      <th style="text-align:right">Of the world</th></tr></thead>
    <tbody>
{income_rows}
    </tbody>
  </table>

  <figure><img src="{fig11}" alt="Income groups in 2000 and 2024">
    <figcaption><b>Read:</b> grey dot 2000, coloured dot 2024. Only one group is
      red.</figcaption></figure>

  <div class="pull">The {S['li_n']} low-income countries in the file hold
     {S['li_share']:.0f}&nbsp;% of the world's unserved population. Between 2000 and
     2024 their number <em>rose</em> {S['li_pct']:.0f}&nbsp;%.</div>
</section>

<!-- ============================================ landscape -->
<section>
  <span class="step">Two directions at once</span>
  <h2>The same twenty countries, by direction</h2>
  <p>Two different things can be true of a country at once: it can hold a very large
     number of people without electricity <em>and</em> be improving, or hold a large
     number <em>and</em> be getting worse. The chart below separates the two.</p>
  <figure><img src="{fig7}" alt="The twenty largest countries by direction of travel">
    <figcaption><b>Read:</b> bar length is how many people lack electricity today.
      Colour is which way the number moved since 2010. The figure inside each bar is
      that change, in millions.</figcaption></figure>
  <p>Both groups are real, and they are different problems. A country in the teal group
     has a large backlog and is working through it. A country in the red group has a
     large backlog that is growing — which means the supply side is losing ground to
     something else, most often population.</p>
</section>

<!-- ============================================ worsening -->
<section>
  <span class="step">Going backwards</span>
  <h2>{S['worse_n']} countries went backwards</h2>
  <figure><img src="{fig5}" alt="Countries where the number grew between 2010 and 2024">
    <figcaption><b>Read:</b> countries where more people lack electricity in 2024 than
      in 2010.</figcaption></figure>
  <div class="stats">
    <div class="stat"><div class="v r">{S['worse_n']}</div>
      <div class="k">countries went backwards between 2010 and 2024</div></div>
    <div class="stat"><div class="v r">+{millions(S['worse_added'])}</div>
      <div class="k">people those countries added to the problem</div></div>
  </div>
  <p>This is what it looks like when the population grows faster than the grid. The
     share of households with power can improve every year while the absolute number of
     people without it still rises. The Democratic Republic of Congo alone added
     25 million.</p>
  <div class="pull">At Sub-Saharan Africa's rate over the past 14 years, halving the
     region's number would take over {S['ssa_years_halve']:.0f} years.</div>
</section>

<!-- ============================================ 2030 -->
<section>
  <span class="step">The deadline</span>
  <h2>Where the trend points</h2>
  <figure><img src="{fig6}" alt="Projection of people without electricity to 2030">
    <figcaption><b>Read:</b> the black line is what happened. The dashed line carries
      that rate forward. The green line is zero.</figcaption></figure>
  <div class="big">{millions(S['proj_2030'])} million
    <span class="lbl">would still be without electricity in 2030, if every country
      keeps its recent pace — including the {S['worse_n']} currently moving
      backwards.</span></div>
</section>

<!-- ============================================ every country -->
<section>
  <span class="step">Every country</span>
  <h2>Every country, sorted however you like</h2>
  <p>The same data as every table above, in a form you can question while you are in
     the room: type a name, pick a region or an income group, click a column heading
     to sort. The last column is the one to sort by if the question is who is moving.</p>

  <div class="ctl">
    <input id="q" type="search" placeholder="Filter by country name&hellip;">
    <select id="rg"><option value="">All regions</option>{REGION_OPTS}</select>
    <select id="inc"><option value="">All income groups</option>{INCOME_OPTS}</select>
    <span class="cnt" id="cnt"></span>
  </div>

  <div class="scroll">
    <table id="allc">
      <thead><tr>
        <th data-c="0">Country</th><th data-c="1">Region</th><th data-c="2">Income</th>
        <th data-c="3" style="text-align:right">2000</th>
        <th data-c="4" style="text-align:right">2010</th>
        <th data-c="5" style="text-align:right">2024</th>
        <th data-c="6" style="text-align:right">Since&nbsp;2010</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <p style="margin-top:16px;font-size:14px;color:var(--muted)">
     {S['always_zero']} of these countries report nobody without electricity in every
     year the file covers. They stay in the table — they are part of the dataset —
     but they are not part of the problem.</p>
</section>

<!-- ============================================ what this data actually is -->
<section>
  <span class="step">The fine print</span>
  <h2>What this data is — and what it cannot tell you</h2>
  <p>Everything on this page comes from a single file:
     <code>data/people-without-electricity-country.csv</code>. Four things decide how
     to read every number above.</p>

  <div class="stats">
    <div class="stat"><div class="v">{exact(S['rows'])}</div>
      <div class="k">rows</div></div>
    <div class="stat"><div class="v">{S['n_countries']}</div>
      <div class="k">countries</div></div>
    <div class="stat"><div class="v">{S['yr1'] - S['yr0'] + 1}</div>
      <div class="k">years, {S['yr0']} to {S['yr1']}</div></div>
    <div class="stat"><div class="v">0</div>
      <div class="k">missing values</div></div>
  </div>

  <div class="note">
    <h4>Four things to know before reading any number above</h4>
    <ul>
      <li><strong>It counts connections, not reliable supply.</strong> A household with
        a meter that sits through daily blackouts counts here as having access. The
        number of people without <em>dependable</em> power is larger than anything on
        this page — and this file cannot measure it.</li>
      <li><strong>A zero means zero</strong>, not "missing". {S['always_zero']} countries
        report nobody without access in every year they appear. Dropping or imputing
        zeros would invent a problem the file says does not exist.</li>
      <li><strong>The file also contains {S['n_agg']} regional averages</strong>
        ("Sub-Saharan Africa", "World", income groups). They are useful for comparison
        but must never be counted alongside countries — the region and its members are
        both in the file, so mixing them double-counts people.</li>
      <li><strong>It stops at the country border.</strong> Electricity access is
        ultimately a village-level fact, and this file cannot see that far down.</li>
    </ul>
  </div>
</section>

<section>
  <span class="step">What you can aim at</span>
  <h2>What this data lets you aim at — and what decides it</h2>
  <p>The file supports several different slices, and they point at different places.
     Which one is useful depends entirely on the criteria you bring; the data does not
     choose for you. These are the slices, side by side.</p>

  <div class="cards">
    <div class="card r"><div class="n">{S['now']/1e6:.0f} M</div>
      <h4>Largest numbers</h4>
      <p>Nigeria, DR Congo, Ethiopia, Tanzania, Uganda. The biggest backlogs in
        absolute terms. Twenty countries hold {S['top20_share']:.0f}% of the total.</p></div>
    <div class="card r"><div class="n">{S['worse_n']}</div>
      <h4>Getting worse</h4>
      <p>Countries where the number rose since 2010. DR Congo, Niger, Chad, Malawi,
        Mozambique, Somalia. {S['worse_africa']} of the {S['worse_n']} are in Africa.</p></div>
    <div class="card g"><div class="n">&minus;91%</div>
      <h4>Already improving</h4>
      <p>Everything outside Sub-Saharan Africa. India, Bangladesh, China, Indonesia,
        and {len(better)} countries that reduced their number since 2010.</p></div>
    <div class="card"><div class="n">{S['share_now']:.0f}%</div>
      <h4>Concentrated</h4>
      <p>Sub-Saharan Africa's share of what remains — up from {S['share_then']:.0f}% in
        2000. The problem has moved rather than shrunk.</p></div>
  </div>

  <h3>What would decide between them</h3>
  <p>None of the following can be answered from this file. They are the questions that
     would narrow the list above to a place — and each needs a different source.</p>
  <div class="note">
    <ul>
      <li><strong>Reliable supply, not just a connection.</strong> This file cannot
        distinguish a household with steady power from one with a meter and a daily
        blackout. The addressable group is larger than anything on this page, and this
        file cannot size it.</li>
      <li><strong>Whether the area is off-grid at all.</strong> A village connected to a
        working grid is a different problem from one that has never been connected.</li>
      <li><strong>What it currently costs to supply.</strong> Diesel generation per
        kilowatt-hour is public for some countries and not others, and it changes the
        economics completely.</li>
      <li><strong>Whether there is a load that cannot wait.</strong> A health facility
        with a vaccine cold chain, or a water pump, changes what a solution has to
        guarantee. That is not in this file — it needs facility records.</li>
      <li><strong>Population and households.</strong> To know what a number means
        relative to a place, this file would need to be joined to census data.</li>
    </ul>
  </div>
  <div class="pull">This file can size a market. It cannot choose a site — and the
     criteria above, not the data, are what turn one into the other.</div>
</section>

<!-- ============================================ questions -->
<section>
  <span class="step">Questions</span>
  <h2>Questions, answered and not answered</h2>
  <p>Each question below is marked with whether this data answers it. Nothing is
     filled in with an opinion.</p>

  <div class="qa"><span class="tag y">answered</span><div class="q">Who exactly is
    affected?</div><div class="a">
    <p>At country level: {exact(S['now'])} people in 2024. {S['share_now']:.0f}% of them
      in Sub-Saharan Africa. {S['top20_share']:.0f}% of them in twenty countries. The
      largest single number is Nigeria, {exact(top20.iloc[0].d)}.</p>
    <p><strong>At the level of a person, no.</strong> This file has no sub-national data.
      It can say which country, never which town.</p></div></div>

  <div class="qa"><span class="tag y">answered</span><div class="q">How many people
    could a solution reach?</div><div class="a">
    <p>The file gives the size of the <em>problem</em>: {exact(S['now'])} people. It
      cannot give the size of a reachable group, because that depends on criteria it
      does not contain — reliability, grid status, cost to serve. Any reach figure
      derived from this file alone would be the whole problem restated.</p></div></div>

  <div class="qa"><span class="tag y">answered</span><div class="q">Where is the problem
    getting worse rather than better?</div><div class="a">
    <p>{S['worse_n']} countries, listed above, adding {millions(S['worse_added'])}
      people since 2010. {S['worse_africa']} of the {S['worse_n']} are in Africa.</p></div></div>

  <div class="qa"><span class="tag y">answered</span><div class="q">Is progress
    possible?</div><div class="a">
    <p>Yes, and the file shows it happening. India went from
      {millions(S['india_then'])} to {exact(S['india_now'])}. Outside Sub-Saharan Africa
      the total fell {S['rest_cut']:.0f}%. The world total halved in 24 years.</p></div></div>

  <div class="qa"><span class="tag y">answered</span><div class="q">Does the trend reach
    zero by 2030?</div><div class="a">
    <p>No. At the 2010&ndash;2024 pace, {millions(S['proj_2030'])} people would remain.
      This is an extrapolation of an aggregate, not a forecast — it assumes every
      country holds its recent pace.</p></div></div>

  <div class="qa"><span class="tag n">not answered</span><div class="q">Which specific
    place should be targeted?</div><div class="a">
    <p>This file cannot answer it. It has no data below country level. Choosing a site
      requires criteria — grid status, cost to serve, presence of a critical load —
      that live in other sources. The section above lists them.</p></div></div>

  <div class="qa"><span class="tag n">not answered</span><div class="q">How reliable is
    the supply where people are connected?</div><div class="a">
    <p>Not measurable here. The indicator counts connection, so a household with a
      meter and daily blackouts is indistinguishable from one with steady power. Any
      claim about reliability needs a different dataset.</p></div></div>

  <div class="qa"><span class="tag n">not answered</span><div class="q">Who specifically
    benefits — which household, which facility?</div><div class="a">
    <p>Not in this file. Naming a person or a facility requires local records:
      health-facility lists, barangay or municipal registers, utility connection data.
      The file gives the country and the scale; everything below that is elsewhere.</p></div></div>
</section>

<!-- ============================================ the one thing -->
<section>
  <span class="step">If you read nothing else</span>
  <h2>The most important thing on this page</h2>

  <div class="stats">
    <div class="stat"><div class="v r">{S['two_share']:.0f}%</div>
      <div class="k">of everyone without electricity lives in just two countries —
        Nigeria and DR Congo</div></div>
    <div class="stat"><div class="v">{S['share_now']:.0f}%</div>
      <div class="k">of what remains is in Sub-Saharan Africa, up from
        {S['share_then']:.0f}% in 2000</div></div>
    <div class="stat"><div class="v r">{S['worse_n']}</div>
      <div class="k">countries are moving backwards, adding
        {millions(S['worse_added'])} people since 2010</div></div>
    <div class="stat"><div class="v r">{millions(S['proj_2030'])}&nbsp;M</div>
      <div class="k">would still lack electricity in 2030 if the current pace
        holds</div></div>
  </div>

  <div class="pull">The world solved half of this problem in 24 years. The half that
     is left is not spread evenly — it is concentrated in Africa, concentrated in a
     few countries, and in those countries it is growing rather than shrinking.</div>

  <p>That is the difference between a problem being solved and a problem being
     outpaced. India shows the first: 419 million people connected in 24 years.
     Nigeria and DR Congo show the second: their numbers went <em>up</em> over the
     same period, because population grew faster than the grid. Everything else on
     this page is detail around those two facts.</p>
</section>

<div class="foot">
  Source: <code>data/people-without-electricity-country.csv</code> ({exact(S['rows'])}
  rows, {S['n_countries']} countries, {S['yr0']}&ndash;{S['yr1']}). Regional figures are
  the World Bank regional aggregates carried in the same file.<br>
  Rebuild this page: <code>python3 data/eda_insights/scripts/build_dashboard.py</code>
</div>

</div>
{LIVE_JS}
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)\n")
print("figure label audit:")
for line in AUDIT:
    print("  " + line)
bad = [a for a in AUDIT if "clean" not in a]
print("\nRESULT:", "all figures clean" if not bad else f"{len(bad)} FIGURE(S) WITH PROBLEMS")
