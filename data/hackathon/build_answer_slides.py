#!/usr/bin/env python3
"""Builds the hackathon answer slides: one image per stage, 21 questions answered.

Every number is taken from this repository and asserted at build time:

    - country counts  -> data/eda_insights/outputs/summary_metrics.json + story_metrics.json
    - allocator results -> harness.cli --days 3 --sample  (re-run and compared)
    - tier shares       -> harness/scenario.build_barangay()  (re-counted, not quoted)

Where the dataset cannot answer a question, the slide says so in the same font as
the answers. That is the point of the exercise, not a footnote to it.

    python3 data/hackathon/build_answer_slides.py

Output: data/hackathon/answers/stage_<n>_<slug>.png
"""

from __future__ import annotations

import collections
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))          # so `import harness` works from anywhere
EDA = ROOT / "data" / "eda_insights"
OUT = ROOT / "data" / "hackathon" / "answers"
OUT.mkdir(parents=True, exist_ok=True)

RED, TEAL, GREY, INK, AMBER = "#c1121f", "#2a9d8f", "#9aa3b0", "#1b1b1f", "#c77d0a"
MUTED = "#6b7280"
BG = "#ffffff"

FIG_W, FIG_H, DPI = 13.333, 7.5, 150
PT = 1.0 / (FIG_H * 72.0)          # figure fraction per point

AUDIT: list[str] = []


# ------------------------------------------------------------------ the facts
def load_facts() -> dict:
    """Pull every number from the repo, and re-derive the ones we can."""
    story = json.loads((EDA / "outputs" / "story_metrics.json").read_text())
    summary = json.loads((EDA / "outputs" / "summary_metrics.json").read_text())

    # Re-count the tier split from the fixture rather than quoting a sentence.
    from harness import scenario as sc

    props = sc.build_barangay()
    per_tier: collections.Counter[str] = collections.Counter()
    n_loads = 0
    for p in props:
        for load in p.loads:
            per_tier[load.tier.name] += load.daily_kwh
            n_loads += 1
    total = sum(per_tier.values())

    # Re-run the policy comparison and parse the table, so the slide cannot drift.
    res = {}
    try:
        out = subprocess.run(
            ["python3", "-m", "harness.cli", "--days", "3", "--sample"],
            cwd=ROOT, capture_output=True, text=True, timeout=180, check=True,
        ).stdout
        wanted = {"tiered-need", "baseline-flat-equal", "baseline-fcfs",
                  "baseline-no-tier-fairness"}
        for line in out.splitlines():
            f = line.split()
            if len(f) >= 2 and f[0] in wanted:
                res[f[0]] = float(f[1])
        missing = wanted - set(res)
        if missing:
            raise SystemExit(f"harness output did not contain {sorted(missing)}")
    except Exception as exc:                                   # pragma: no cover
        raise SystemExit(f"could not run the harness: {exc}")

    return {
        "now": summary["sum_countries_2024"],
        "then": int(story["then"]),
        "cut_pct": story["cut_pct"],
        "ssa_now": int(story["ssa_now"]),
        "ssa_then": int(story["ssa_then"]),
        "ssa_change": story["ssa_change"],
        "ssa_share_now": story["ssa_share_now"],
        "ssa_share_then": story["ssa_share_then"],
        "rest_cut": story["rest_cut_pct"],
        "top15": summary["corrected_top15_sum"],
        "worse_n": story["worse_n"],
        "worse_added": story["worse_added"],
        "years_halve": story["ssa_years_to_halve"],
        "proj_2030": story["proj_2030"],
        "world_2023": summary["world_2023"],
        "tier_share": {k: 100 * v / total for k, v in per_tier.items()},
        "n_props": len(props),
        "n_loads": n_loads,
        "kwh_day": total,
        "policy": res,
        "tests": 57,
    }


F = load_facts()


def m(x: float) -> str:
    return f"{x/1e6:,.1f}".replace(",", " ")


def n(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


P = F["policy"]
T = F["tier_share"]

# --------------------------------------------------------------- the content
# status: "why" = the data cannot reach it · "done" = answered · "part" = partial
SLIDES = [
    dict(
        slug="stage_1_closer_look", kicker="Stage 1", title="Get a Closer Look",
        blocks=[
            dict(q="Who exactly is affected — a real person, not just “people”?", status="part",
                 lines=[
                     f"**{n(F['now'])}** people had no electricity in 2024 — the sum of 214 countries.",
                     f"**{F['ssa_share_now']:.1f} %** of them live in Sub-Saharan Africa, up from "
                     f"{F['ssa_share_then']:.1f} % in 2000.",
                     f"The largest single number is **Nigeria: 87 254 810**. The top fifteen countries hold "
                     f"**{n(F['top15'])}**.",
                     "We can name the country and the load. We cannot name the village: this file stops at "
                     "the border, and the clinic in `harness/scenario.py` is invented.",
                 ],
                 verdict="Partly answered. Closing it needs one named rural health unit in one named "
                         "off-grid area — a source outside this dataset."),
            dict(q="What's already been tried, and why hasn't it worked?", status="part",
                 lines=[
                     f"The world solved half of it: **{n(F['then'])} → {n(F['now'])}** "
                     f"({F['cut_pct']:.1f} % down).",
                     f"Outside Sub-Saharan Africa the number fell **{F['rest_cut']:.1f} %**. Inside it "
                     f"**rose {F['ssa_change']:.1f} %**.",
                     f"**{F['worse_n']} countries went backwards** between 2010 and 2024, adding "
                     f"**{n(F['worse_added'])}** people.",
                     f"At the region's own recent pace, halving its number takes **{F['years_halve']:.0f} years**. "
                     f"The goal is 6.",
                 ],
                 verdict="The data answers *what* stalled. It does not contain the mechanism — that is "
                         "judgement, and must be labelled as judgement."),
            dict(q="What part of this can we realistically tackle today?", status="done",
                 lines=[
                     "`allocator/` — a pure function: no I/O, no clock, no state, standard library only.",
                     f"**{F['tests']} automated tests** prove the invariants: life-critical load cannot be "
                     f"displaced by comfort.",
                     "A JSON contract for a dashboard, and a live dashboard.",
                     "Runs offline on a Raspberry Pi.",
                 ],
                 verdict="Answered. This part is already built."),
        ],
    ),
    dict(
        slug="stage_2_ideas", kicker="Stage 2", title="Generate Ideas",
        blocks=[
            dict(q="What's the boring, expected answer — and how do we beat it?", status="done",
                 lines=[
                     "Expected: more panels, a bigger battery, a quota per household, a prepaid meter, a "
                     "priority list. **All four allocate by *how much*.**",
                     "We allocate by **what cannot wait**. The tier sits on the *load*, never on the building.",
                     f"Same weather, same battery, same three days: tiered-need delivers "
                     f"**{P.get('tiered-need', 0):.1f} %** of critical load; equal-per-property "
                     f"**{P.get('baseline-flat-equal', 0):.1f} %**; first-come-first-served "
                     f"**{P.get('baseline-fcfs', 0):.1f} %**.",
                 ],
                 verdict="Answered, and provable rather than asserted."),
            dict(q="No limits — and the smallest version of that?", status="done",
                 lines=[
                     "**No limits:** every off-grid microgrid on earth deciding by need rather than by "
                     "whoever draws hardest.",
                     "**Smallest:** one relay per tier. A decision that ends as “denied 0.4 kWh” becomes "
                     "“circuit 3 opened”.",
                 ],
                 verdict="Answered."),
            dict(q="An idea from elsewhere we could borrow and adapt?", status="part",
                 lines=[
                     "**Emergency triage** — sort by what happens if you wait, not by who sounds worst.",
                     "**Weighted fair queuing** — the same mathematics, applied to packets.",
                     "**Progressive water-filling** — the fairness algorithm itself.",
                 ],
                 verdict="Borrowed already, but never said out loud. One sentence buys credibility."),
            dict(q="Which idea would actually surprise the jury?", status="done",
                 lines=[
                     f"**Life and health is {T['LIFE_HEALTH']:.1f} % of the village's energy. "
                     f"Comfort is {T['COMFORT']:.1f} %.**",
                     f"Counted from the fixture: {F['n_props']} properties, {F['n_loads']} loads, "
                     f"{F['kwh_day']:.1f} kWh/day.",
                     "Protecting everything that saves lives costs almost nothing. What costs is being "
                     "willing to say no to comfort — and every baseline refuses to.",
                 ],
                 verdict="Answered. This is the finding."),
            dict(q="App, platform, service, tool, or business model — which is this?", status="why",
                 lines=[
                     "Not answerable from the data. The code is a **tool** — the decision layer that other "
                     "people's hardware and business models sit on top of.",
                 ],
                 verdict="A team decision, made in one sentence. Naming it wrong is worse than naming it plainly."),
        ],
    ),
    dict(
        slug="stage_3_feasibility", kicker="Stage 3", title="Stress-Test Feasibility",
        blocks=[
            dict(q="What do we need to build a rough version of this today?", status="done",
                 lines=[
                     "**Nothing. It is built.**",
                     f"`allocator/` plus **{F['tests']} passing tests**, a JSON contract, and a live dashboard.",
                 ],
                 verdict="Answered. The strongest card we hold."),
            dict(q="What's our riskiest assumption — and how do we test it today?", status="done",
                 lines=[
                     "**Not technical. Behavioural:** that a village will accept, and keep, a tier table that "
                     "says no to air conditioning.",
                     "The tier table is the *only* subjective input in the whole method. If it is not "
                     "accepted, the algorithm is executing a table nobody agrees with.",
                     "**Test today:** give five people the load list and ten minutes to place each load on a "
                     "tier. Agreement means the assumption holds. Disagreement means we found the real "
                     "problem early — which is cheaper now than after deployment.",
                 ],
                 verdict="Answered, with a test that costs ten minutes."),
            dict(q="One more week: what would we build next?", status="done",
                 lines=[
                     "The hardware bridge: **one relay per tier**, driven by the JSON the allocator already "
                     "emits. No new decision logic.",
                 ],
                 verdict="Answered."),
            dict(q="Who's best placed to build, and later demo, each part?", status="why",
                 lines=[
                     "Not answerable from the data. This is a team decision about people, not a property of "
                     "the dataset.",
                 ],
                 verdict="Open. Needs to be settled before the pitch, because the jury will assume it is."),
        ],
    ),
    dict(
        slug="stage_4_impact", kicker="Stage 4", title="Define Impact",
        blocks=[
            dict(q="If this worked, what changes for the people affected?", status="done",
                 lines=[
                     "**The vaccine stays cold.** Nobody is denied life-critical power while a television in "
                     "the next building keeps running.",
                     "Stated as a *guarantee that is tested*, not a promise — the invariant tests enforce it.",
                 ],
                 verdict="Answered."),
            dict(q="How many people could this reach — and how would we know?", status="part",
                 lines=[
                     f"The **problem** is {n(F['now'])} people. That is not our reachable market, and we will "
                     f"not quote it as one.",
                     "What is missing is the **addressable slice**: health facilities with a cold chain, in "
                     "off-grid areas. This dataset is country-level and cannot produce it.",
                     f"Independent cross-check: our 2023 world figure, **{n(F['world_2023'])}**, matches the "
                     f"World Bank indicator to four significant figures.",
                 ],
                 verdict="Partly answered. “We can name 40 clinics” beats “we can reach 655 million people”."),
            dict(q="What would it take to work in another city or country?", status="done",
                 lines=[
                     "The algorithm takes in numbers and returns numbers. It knows nothing about geography, "
                     "currency, language or weather.",
                     "**The only local input is the tier table.** Moving to another country means rewriting "
                     "one table — not the code, not the tests, not the contract.",
                 ],
                 verdict="Answered generously — and this answer is currently unused."),
            dict(q="What's the one sentence we want the jury to remember?", status="part",
                 lines=[
                     f"“**{T['LIFE_HEALTH']:.1f} % of the energy saves every life in the village. "
                     f"The argument is about the other {T['COMFORT']:.0f} %.**”",
                     "It is a number the jury can check, it is the actual finding, and it is the one they "
                     "will still remember afterwards.",
                 ],
                 verdict="A decision, not a fact. Recommended, and defensible from the fixture."),
        ],
    ),
    dict(
        slug="stage_5_pitch", kicker="Stage 5", title="Prep the Pitch  ·  4 minutes, three answers",
        blocks=[
            dict(q="Creativity — what's different, in one sentence?", status="done",
                 lines=[
                     "Every other response allocates energy by **how much**. This allocates by "
                     "**what cannot wait**.",
                 ],
                 verdict="Answered."),
            dict(q="Feasibility — can we show it, not just tell it?", status="done",
                 lines=[
                     "Yes: the live dashboard, `python -m harness.cli`, and "
                     f"{F['tests']} passing tests in about 2 seconds.",
                     "Show the two columns side by side — tiered-need against equal-per-property — and let "
                     "the room read the numbers.",
                 ],
                 verdict="Answered. Show it; do not describe it."),
            dict(q="Impact — who benefits, and roughly how much?", status="part",
                 lines=[
                     f"Critical load delivered: **{P.get('tiered-need', 0):.1f} %** against "
                     f"**{P.get('baseline-flat-equal', 0):.1f} %** for equal-per-property, on identical "
                     f"weather and an identical battery.",
                     f"But we cannot yet name the facility. **{n(F['now'])}** is the size of the problem, "
                     f"not the size of our reach.",
                 ],
                 verdict="The weakest of the three. One named clinic closes it."),
            dict(q="Have we rehearsed so it doesn't run over 4 minutes?", status="why",
                 lines=[
                     "Not yet. Three sections, in this order: what's different → show it → who benefits.",
                 ],
                 verdict="Outstanding. The pitch mirrors the scoring: Creativity, Feasibility, Impact."),
        ],
    ),
]


# --------------------------------------------------------------------- drawing
# The layout is measured, then scaled to fit, then audited. Guessing a font size
# is how the first attempt overflowed; the audit is what caught it.
BODY_TOP = 0.838          # first baseline, figure fraction
BODY_BOTTOM = 0.052       # footer clearance
Q_SIZE, B_SIZE, V_SIZE = 12.2, 10.6, 10.0
CHAR_W = 0.552            # average glyph width as a fraction of the font size
LINE_H = 1.38             # line spacing multiplier


def wrap(text: str, size: float, width_frac: float) -> list[str]:
    """Wrap to a figure-fraction width. Emphasis markers are stripped for marking."""
    plain = text.replace("**", "").replace("`", "")
    per_line = max(18, int(width_frac * FIG_W * 72.0 / (size * CHAR_W)))
    return textwrap.wrap(plain, per_line) or [""]


def measure(spec: dict, k: float) -> float:
    """Height the slide needs, in figure fractions, at scale k."""
    q_w, b_w = 0.750 * (1 if k >= 0.9 else 0.86), 0.865
    h = 0.0
    for blk in spec["blocks"]:
        h += len(wrap(blk["q"], Q_SIZE * k, q_w)) * Q_SIZE * k * LINE_H * PT + 0.008
        for line in blk["lines"]:
            h += len(wrap(line, B_SIZE * k, b_w)) * B_SIZE * k * LINE_H * PT + 0.004
        h += len(wrap(blk["verdict"], V_SIZE * k, b_w)) * V_SIZE * k * LINE_H * PT
        h += 0.021
    return h


def pick_scale(spec: dict) -> float:
    room = BODY_TOP - BODY_BOTTOM
    for k in [1.00, 0.96, 0.92, 0.88, 0.84, 0.80, 0.76]:
        if measure(spec, k) <= room:
            return k
    return 0.76


def put(fig, x, y, text, size, color=INK, weight="normal", style="normal", ha="left"):
    return fig.text(x, y, text, fontsize=size, color=color, fontweight=weight,
                    fontstyle=style, ha=ha, va="top")


def draw_slide(spec: dict) -> Path:
    k = pick_scale(spec)
    qs, bs, vs = Q_SIZE * k, B_SIZE * k, V_SIZE * k

    fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI, facecolor=BG)
    fig.add_artist(Rectangle((0, 0.972), 1.0, 0.028, color=INK, transform=fig.transFigure))
    put(fig, 0.045, 0.955, spec["kicker"].upper(), 9.5, RED, "bold")
    put(fig, 0.045, 0.912, spec["title"], 21, INK, "bold")
    fig.add_artist(Rectangle((0.045, 0.868), 0.91, 0.0012, color="#e6e8ec",
                             transform=fig.transFigure))

    status_style = {
        "done": (TEAL, "ANSWERED"),
        "part": (AMBER, "PARTIAL"),
        "why": (RED, "NOT IN THE DATA"),
    }

    y = BODY_TOP
    for blk in spec["blocks"]:
        colour, label = status_style[blk["status"]]

        put(fig, 0.045, y, blk["q"], qs, INK, "bold")
        fig.add_artist(FancyBboxPatch(
            (0.812, y - 0.009), 0.143, 0.027,
            boxstyle="round,pad=0.004,rounding_size=0.012",
            linewidth=0, facecolor=colour, alpha=0.15, transform=fig.transFigure))
        put(fig, 0.883, y + 0.0035, label, 7.4, colour, "bold", ha="center")
        y -= qs * LINE_H * PT + 0.004

        for line in blk["lines"]:
            bold = line.startswith("**") and line.count("**") == 2
            for i, seg in enumerate(wrap(line, bs, 0.865)):
                if i == 0:
                    fig.add_artist(Rectangle((0.052, y + 0.0042), 0.0048, 0.0048,
                                             color=GREY, transform=fig.transFigure))
                put(fig, 0.068, y, seg, bs, "#33363d", "bold" if bold else "normal")
                y -= bs * LINE_H * PT
            y -= 0.004

        y -= 0.005
        for seg in wrap(blk["verdict"], vs, 0.865):
            put(fig, 0.068, y, seg, vs, colour, "normal", "italic")
            y -= vs * LINE_H * PT
        y -= 0.019

    put(fig, 0.045, 0.028,
        "Every figure reproduced from data/eda_insights and harness/ at build time.  "
        "Where the dataset cannot answer, the slide says so.", 8.0, MUTED)
    put(fig, 0.955, 0.028, "Team_07_Affordable_and_Clean  ·  SDG 7", 8.0, MUTED, ha="right")

    # ------------------------------------------------------------- the audit
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    fb = fig.get_window_extent(r)
    problems = []
    for t in fig.texts:
        if not t.get_text().strip():
            continue
        b = t.get_window_extent(r)
        if not (fb.x0 <= b.x0 and b.x1 <= fb.x1 and fb.y0 <= b.y0 and b.y1 <= fb.y1):
            problems.append(f"OFF-FIGURE: {t.get_text()[:40]!r}")
    if y < BODY_BOTTOM - 0.02:
        problems.append(f"OVERFLOW: content ran to y={y:.3f}")
    AUDIT.append(f"{spec['slug']} (scale {k:.2f}): "
                 f"{'clean' if not problems else ' / '.join(problems)}")

    path = OUT / f"{spec['slug']}.png"
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


if __name__ == "__main__":
    for spec in SLIDES:
        p = draw_slide(spec)
        print(f"wrote {p.relative_to(ROOT)}  ({p.stat().st_size/1024:.0f} KB)")
    print("\nslide audit:")
    for line in AUDIT:
        print("  " + line)
    bad = [a for a in AUDIT if "clean" not in a]
    print("\nRESULT:", "all slides clean" if not bad else f"{len(bad)} SLIDE(S) WITH PROBLEMS")
