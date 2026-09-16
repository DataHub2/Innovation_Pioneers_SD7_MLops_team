#!/usr/bin/env python3
"""Builds the hackathon brief: a self-contained page answering the 20 questions.

Sister page to the data dashboard. The dashboard stays data-only; this page
answers the brief, using the data in this repo plus the project decisions.

    python3 data/hackathon/build_brief.py

Output: data/hackathon/brief.html
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDA = ROOT / "data" / "eda_insights"
OUT = ROOT / "data" / "hackathon" / "brief.html"

metrics = json.loads((EDA / "outputs" / "summary_metrics.json").read_text())
story = json.loads((EDA / "outputs" / "story_metrics.json").read_text())


def b64(name: str) -> str:
    p = EDA / "figures" / name
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


FIG_DIVORCE = b64("story_3_divorce.png")
FIG_BACKWARDS = b64("story_5_backwards.png")

S = dict(story, **metrics)

# ---------------------------------------------------------------- content
# Each entry: (question, status, answer_html)
STAGES = [
    ("Stage 1", "Get a Closer Look", [
        ("Who exactly is affected — a real person, not just &ldquo;people&rdquo;?", "open", f"""
<p><strong>We have the problem, not the person.</strong> The dataset gives us
   {S['sum_countries_2024']:,} people without electricity in 2024, of whom
   {S['ssa_share_2024_pct']}% are in Sub-Saharan Africa and {S['corrected_top15_sum']/1e6:.0f} million
   are in the top fifteen countries alone.</p>
<p>The clinic and household in <code>harness/scenario.py</code> — the vaccine cold
   chain, the home dialysis — are <em>invented</em>. They are plausible, and they are
   not real.</p>
<p><strong>What is missing:</strong> one named rural health unit in one named off-grid
   area. That single fact converts &ldquo;655 million people&rdquo; into
   &ldquo;this clinic, this island, this vaccine fridge&rdquo;.</p>
<p class="small"><strong>Where to get it:</strong> the NPC&ndash;SPUG database
   (<code>report.napocor.gov.ph/spugdb/</code>, login required) names the areas and
   meters their generation; the SPUG area pages list diesel plants by municipality;
   DOH facility lists give the health unit and its cold chain.</p>"""),

        ("What's already been tried, and why hasn't it worked?", "partial", f"""
<p><strong>We can answer <em>what</em> failed, from the data:</strong> the world did
   solve most of this — {S['sum_countries_2024']:,}
   today against 1 329 068 818 in 2000. But outside Sub-Saharan Africa the number fell
   {S['rest_cut_pct']}%, while inside it rose 14.5%.
   {S['countries_worse_2010_2024']} countries went backwards, adding
   {S['people_added_by_worsening_countries']/1e6:.0f} million people. At Sub-Saharan
   Africa's recent pace, halving the region takes 334 years.</p>
<p><strong>We cannot yet answer <em>why</em>.</strong> The data shows population
   outrunning the grid. It does not show the mechanism.</p>
<p class="small"><strong>Missing:</strong> one page on cost per km of grid extension,
   terrain, and the NPC&ndash;SPUG diesel subsidy — plus why household solar (PAYG)
   never protected clinics: PAYG sells to households, and a vaccine fridge is
   nobody's customer.</p>"""),

        ("What part of this can we realistically tackle today?", "answered", """
<p><strong>This part is already built.</strong></p>
<ul>
  <li><code>allocator/</code> — a pure function. No I/O, no clock, no state, stdlib only.</li>
  <li><strong>57 automated tests</strong> proving the invariants: critical load cannot be
      displaced by comfort; nobody on a tier can starve another; credits cannot buy
      past a critical load.</li>
  <li>60 properties in 5.8 ms, 500 in 43.7 ms. Runs offline on a Raspberry Pi.</li>
  <li>A JSON contract for the dashboard — written, and consuming a live dashboard.</li>
</ul>"""),
    ]),

    ("Stage 2", "Generate Ideas", [
        ("What's the boring, expected answer — and how do we beat it?", "answered", f"""
<p>The expected answers are all the same shape: <strong>make more energy, or cap how
   much each person takes.</strong> More panels. A bigger battery. A quota per
   household. A prepaid meter. A priority list of <em>who</em> matters.</p>
<p>All five allocate by <strong>how much</strong>. We allocate by <strong>what cannot
   wait</strong>, and the tier sits on the <em>load</em>, never on the building.</p>
<p>It is provable rather than asserted. Same village, same weather, same battery —
   only the allocation rule changes:</p>
<table class="mini">
  <tr><th>Policy</th><th>Critical power delivered</th><th>Unserved critical</th></tr>
  <tr class="ours"><td>Load ladder (ours)</td><td><strong>89.9%</strong></td><td><strong>9.2 kWh</strong></td></tr>
  <tr><td>Equal per property</td><td>33.2%</td><td>64.4 kWh</td></tr>
  <tr><td>First come, first served</td><td>49.8%</td><td>54.2 kWh</td></tr>
  <tr><td>Max-min without a ladder</td><td>53.8%</td><td>50.6 kWh</td></tr>
</table>"""),

        ("No limits: what would we build? Now, the smallest version of that?", "answered", """
<p><strong>No limits:</strong> every off-grid microgrid on earth deciding by need
   rather than by whoever draws hardest.</p>
<p><strong>Smallest version:</strong> one relay per tier. A decision that today ends as
   &ldquo;denied 0.4 kWh&rdquo; becomes &ldquo;circuit 3 opened&rdquo;. That is the
   smallest thing that is still the real thing — and it is a change to the hardware,
   not to the algorithm, which already emits the decision.</p>"""),

        ("Is there an idea from elsewhere we could borrow and adapt?", "partial", """
<p>We have borrowed from three places and never said so out loud:</p>
<ul>
  <li><strong>Emergency triage</strong> — sort by what happens if you wait, not by how
      urgent someone sounds. This is the load ladder.</li>
  <li><strong>Weighted fair queuing</strong> in networking — the same mathematics,
      applied to packets instead of households.</li>
  <li><strong>Progressive water-filling</strong> — the fairness algorithm itself.</li>
</ul>
<p class="small">Costs one sentence in the pitch and buys real credibility: the method
   is not invented from nothing, it is a principle medicine and networking already
   run on, applied to energy.</p>"""),

        ("Which idea would actually surprise the jury?", "answered", f"""
<div class="kicker-stat">5.5%</div>
<p class="stat-label">of the village's energy is everything life-critical —
   vaccine cold chain, dialysis, drinking water. Comfort is
   <strong>46.0%</strong>.</p>
<p>The entire argument about allocation is about the 46% that is air conditioning and
   televisions. <strong>Protecting everything that saves lives costs almost
   nothing.</strong> What costs is being willing to say no to comfort — and every
   baseline in the comparison refuses to.</p>"""),

        ("App, platform, service, tool, or business model — which is this, really?", "open", """
<p>We have never answered this, and the brief asks it directly.</p>
<p><strong>My recommendation: a tool.</strong> It is a decision layer with a defined API
   — it takes numbers, returns numbers and reasons. It is not an app (no user
   interface), not a service (nothing is operated), and claiming a business model we
   have not built is the one answer that can lose points for honesty.</p>
<p class="small">Sell it, donate it, or embed it — but say <em>tool</em>, and let the
   hardware and the business models be other people's layers.</p>"""),
    ]),

    ("Stage 3", "Stress-Test Feasibility", [
        ("What do we need to build a rough version of this today?", "answered", """
<p><strong>Nothing.</strong> It is built, tested and runnable right now:</p>
<pre><code>python -m pytest -q                          # 57 passed
python -m harness.cli --days 3 --sample      # live comparison
python -m harness.cli --days 3 --json out.json</code></pre>
<p>This is our strongest answer in the whole brief.</p>"""),

        ("What's our riskiest assumption — how do we test it today?", "answered", """
<p><strong>The riskiest assumption is not technical. It is behavioural:</strong></p>
<blockquote>That a village will accept, and keep, a tier table that says no to air
   conditioning.</blockquote>
<p>Everything downstream depends on it. The tier table is the only subjective input in
   the method — if it is not accepted and stable, the algorithm is faithfully
   executing a table nobody agrees with.</p>
<p>Second-riskiest: that our voluntary-curtailment model (households switch off comfort
   when the battery runs low) resembles real behaviour. In the simulation it is
   assumed; in reality it needs a price signal or an agreement.</p>
<p><strong>How to test it today, without a village:</strong> the tier table takes ten
   minutes to show anyone. Give the load list to five people and ask each to place
   every load on a tier. Agreement means the assumption holds. Disagreement is the
   real finding — and far cheaper to discover now than after deployment.</p>"""),

        ("One more week: what would we build next?", "answered", """
<p>The hardware bridge: <strong>one relay per tier</strong>, driven by the JSON the
   algorithm already emits. It is the shortest path from &ldquo;a decision&rdquo; to
   &ldquo;something visibly switches&rdquo; — which is also what the pitch needs.</p>"""),

        ("Who's best placed to build, and later demo, each part?", "open", """
<p>Not answered anywhere. This needs a team decision, not analysis. Worth filling in
   before the pitch so each person knows their segment.</p>"""),
    ]),

    ("Stage 4", "Define Impact", [
        ("If this worked, what changes for the people affected?", "answered", """
<p><strong>The vaccine stays cold. Nobody is denied life-critical power while a
   television in the next building keeps running.</strong></p>
<p>That is the whole change — and it is stated in the project as a guarantee that is
   <em>tested</em>, not promised: three invariants, proven by 57 automated tests.</p>"""),

        ("How many people could this reach — and how would we know?", "partial", f"""
<p><strong>The top of the funnel is solid and cross-checked:</strong></p>
<ul>
  <li>{S['sum_countries_2024']:,} people without access in 2024.</li>
  <li>{S['ssa_share_2024_pct']}% of them in Sub-Saharan Africa.</li>
  <li>Independently verified: our derived world figure for 2023
      ({S['crosscheck_method_md']['world_2023_from_csv']:,}) matches the World Bank
      indicator, computed a different way, to four significant figures.</li>
</ul>
<div class="warn"><strong>Do not quote 655 million as our market.</strong> That is the
   size of the problem. Our addressable slice is <em>health facilities with a cold
   chain, in off-grid areas</em> — and this dataset is country-level, so it cannot
   produce that number.</div>
<p>&ldquo;We can name 40 clinics&rdquo; beats &ldquo;we can reach 655 million
   people&rdquo;, and a jury will check.</p>"""),

        ("What would it take to work in another city or country?", "answered", """
<p><strong>Better than we have claimed.</strong> The algorithm receives numbers and
   returns numbers. It knows nothing about geography, currency, language or weather.</p>
<p><strong>The only local input is the tier table.</strong> Moving to another country
   means rewriting one table — not the code, not the tests, not the contract.</p>
<p>That is a genuinely strong answer to a question we currently answer badly, and it
   is sitting unused.</p>"""),

        ("What's the one sentence we want the jury to remember?", "open", """
<p>Needs a decision. Candidates, all drawn from the data:</p>
<ol>
  <li>&ldquo;The village doesn't have a shortage of energy. It has a shortage of
      order.&rdquo;</li>
  <li>&ldquo;You cannot run a clinic on a first-come-first-served tariff.&rdquo;</li>
  <li>&ldquo;5.5% of the energy saves every life in the village. The argument is about
      the other 46%.&rdquo;</li>
</ol>
<p><strong>Recommendation: (3).</strong> It is a number the jury can check, it is the
   actual finding, and it is the one they will still remember afterwards.</p>"""),
    ]),

    ("Stage 5", "Prep the Pitch", []),
]

PITCH = [
    ("Creativity: what's different, in one sentence?",
     "open", "Use the one-sentence choice above. Do not describe the method — state the difference."),
    ("Feasibility: can we show it, not just tell it?",
     "answered", "Yes. Live dashboard, live <code>python -m harness.cli</code>, 57 passing tests. Show, don't narrate."),
    ("Impact: who benefits, and roughly how much?",
     "partial", "Blocked on naming the facility. Until then, speak about the cold chain, not the billion."),
    ("Rehearsed so it doesn't run over 4 minutes?",
     "open", "Not yet. The pitch is three answers in order — Creativity, Feasibility, Impact — because that is exactly what is scored."),
]

RECOMMENDATION = f"""
<p class="small">This is the part that existed only in conversation and had never been
   written down. It answers <em>&ldquo;who exactly, and where&rdquo;</em> — the first
   question in the brief.</p>

<h4>The bet</h4>
<p><strong>Sub-Saharan Africa — but not as a geography play. As a load play:
   the vaccine cold chain. Entering through East Africa.</strong></p>

<h4>Three reasons</h4>
<ol>
  <li><strong>Where the problem is.</strong> {S['ssa_share_2024_pct']}% of the global
      deficit, and {S['countries_worse_2010_2024']} countries going backwards — 17 of
      them in Africa. That is arithmetic, not judgement.</li>
  <li><strong>Where the algorithm's story lands.</strong> The method's whole claim is
      that life-critical load can never be displaced by comfort. In the Philippines
      that is an optimisation story. In Sub-Saharan Africa it is &ldquo;the vaccine was
      ruined and a child was not immunised&rdquo;. Same code, different stakes — and
      the second opens doors at Gavi, WHO and health ministries. The buyer already
      exists and already has a budget.</li>
  <li><strong>Where we can actually execute.</strong> Kenya, Tanzania and Uganda —
      roughly 68 million people combined. Anglophone, functioning cold-chain
      programmes, an off-the-shelf solar PAYG ecosystem (so we do not build hardware,
      technicians and financing from zero), and all three on a downward trend: we ride
      the current instead of fighting it.</li>
</ol>

<h4>Why not the Philippines</h4>
<p>It is the comfortable choice and I would resist it. Yes: verified data, public
   NPC&ndash;SPUG diesel costs, an institutional buyer. But rural access is
   <strong>97.6%</strong> and the deficit fell from 20.1 million to 6.0 million since
   2000. The project's own figure — 2.3 million — is a <em>ceiling, not a runway</em>.</p>
<p>Keep it, but demote it from &ldquo;market&rdquo; to <strong>reference
   deployment</strong>: it de-risks the demo and supplies the diesel-cost benchmark for
   the economics. Just not the bet.</p>

<h4>The honest problem with this recommendation</h4>
<p>The countries where the deficit is <em>growing</em> — DR Congo (+25 M), Niger, Chad,
   Malawi, South Sudan — are exactly where deployment is hardest. East Africa is where
   it is <em>shrinking</em>. There is a real tension between &ldquo;biggest
   problem&rdquo; and &ldquo;deployable&rdquo;.</p>
<p><strong>Resolution: prove it in East Africa, aim at Central and West Africa.</strong>
   Stated plainly — if the team's real strength is field operations rather than
   product, the answer flips, and DR Congo and Nigeria become the prize despite being
   the hardest.</p>

<h4>What to verify before committing</h4>
<p>Three questions, three sources, never mixed up:</p>
<ul>
  <li>Is there a health facility with a cold chain in the target area? → creates the
      tier-1 load, which is the whole point.</li>
  <li>What does diesel cost per kWh there? → the economic argument.</li>
  <li>Is the area off-grid, or connected-but-unreliable? → decides whether islanded
      mode is even right.</li>
</ul>
<div class="warn">None of these are answerable from our dataset. It is country-level.
   That is itself the finding: <strong>the file can size the market, but it cannot
   choose a village</strong> — and the village decides whether the project works.</div>
"""

NEXT = [
    ("Name a facility", "One rural health unit, one off-grid area. Closes the first and loudest question and gives Impact a real number.", "open"),
    ("Pick the one sentence", "Recommendation (3). Decide it, and say it the same way every time.", "open"),
    ("Answer &ldquo;tool or business model&rdquo;", "One sentence, defensible. Recommendation: a tool.", "open"),
    ("Write the &ldquo;why it hasn't worked&rdquo; page", "The data gives the what. We still owe the why.", "partial"),
    ("Say where the idea came from", "Triage, fair weighted queuing, water-filling. One line, high credibility.", "partial"),
    ("Rehearse to 4 minutes", "Three sections: what's different, show it, who benefits.", "open"),
]

BADGE = {"answered": ("Answered", "b"), "partial": ("Partial", "a"), "open": ("Open", "r")}


def stage_html(title, subtitle, items):
    if not items:
        rows = "\n".join(
            f"""<div class="qa">
      <div class="q"><span class="dot {BADGE[st][1]}"></span>{q}</div>
      <div class="a">{a}</div></div>""" for q, st, a in PITCH)
        return f"""<section><h2>{title} <span class="sub">· {subtitle}</span></h2>{rows}</section>"""
    rows = "\n".join(
        f"""<div class="qa">
      <div class="q"><span class="dot {BADGE[st][1]}"></span>{q}
        <span class="tag {BADGE[st][1]}">{BADGE[st][0]}</span></div>
      <div class="a">{a}</div></div>""" for q, st, a in items)
    return f"""<section><h2>{title} <span class="sub">· {subtitle}</span></h2>{rows}</section>"""


body = "\n".join(stage_html(*s) for s in STAGES)

ALL = [(st) for _, _, items in STAGES for _, st, _ in items] + [st for _, st, _ in PITCH]
n_ans = ALL.count("answered")
n_par = ALL.count("partial")
n_open = ALL.count("open")
assert n_ans + n_par + n_open == 20, f"expected 20 questions, counted {len(ALL)}"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hackathon brief — where we stand</title>
<style>
  :root {{ --ink:#1b1b1f; --muted:#6b7280; --line:#e6e8ec; --bg:#f7f8fa;
          --red:#c1121f; --teal:#2a9d8f; --amber:#c77d0a; --card:#fff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16.5px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:0 26px 90px; }}

  header {{ background:var(--ink); color:#fff; padding:60px 0 54px; }}
  header .wrap {{ padding-bottom:0; }}
  .kicker {{ text-transform:uppercase; letter-spacing:.16em; font-size:11.5px;
    font-weight:700; color:#ff8b93; margin-bottom:20px; }}
  header h1 {{ font-size:clamp(28px,5vw,42px); margin:0 0 14px; letter-spacing:-.03em;
    line-height:1.15; font-weight:800; }}
  header .q {{ font-size:clamp(17px,2.4vw,21px); color:#e8e9ee; margin:0;
    max-width:34ch; }}
  header .meta {{ margin-top:30px; font-size:14px; color:#9ea3ad; }}

  .scorecards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
    gap:14px; margin:34px 0 8px; }}
  .sc {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:18px 20px; }}
  .sc .t {{ font-size:12px; text-transform:uppercase; letter-spacing:.1em;
    color:var(--muted); font-weight:700; }}
  .sc .v {{ font-size:19px; font-weight:800; margin-top:7px; letter-spacing:-.02em; }}
  .sc .d {{ font-size:13.5px; color:var(--muted); margin-top:5px; line-height:1.45; }}
  .sc.s1 {{ border-top:4px solid var(--teal); }}
  .sc.s2 {{ border-top:4px solid var(--amber); }}
  .sc.s3 {{ border-top:4px solid var(--red); }}

  .tally {{ display:flex; gap:12px; flex-wrap:wrap; margin:26px 0 0; font-size:14px; }}
  .tally div {{ background:var(--card); border:1px solid var(--line);
    border-radius:999px; padding:7px 16px; font-weight:600; }}
  .tally .b {{ color:var(--teal); }} .tally .a {{ color:var(--amber); }}
  .tally .r {{ color:var(--red); }}

  section {{ padding:48px 0 4px; }}
  h2 {{ font-size:clamp(21px,3.4vw,27px); letter-spacing:-.02em; margin:0 0 18px;
    font-weight:750; border-bottom:2px solid var(--ink); padding-bottom:10px; }}
  h2 .sub {{ color:var(--muted); font-weight:500; }}
  h4 {{ font-size:16px; margin:22px 0 8px; }}
  p {{ max-width:70ch; }}
  ol, ul {{ max-width:70ch; padding-left:22px; }} li {{ margin-bottom:6px; }}
  .small {{ font-size:14px; color:var(--muted); }}
  code {{ background:#eef0f4; padding:2px 6px; border-radius:5px; font-size:14px;
    font-family:ui-monospace,Menlo,Consolas,monospace; }}
  pre {{ background:#1b1b1f; color:#e8e9ee; padding:16px 18px; border-radius:10px;
    overflow-x:auto; font-size:13.5px; line-height:1.7; }}
  pre code {{ background:none; color:inherit; padding:0; }}

  .qa {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:20px 24px; margin-bottom:14px; }}
  .q {{ font-weight:700; font-size:17px; line-height:1.4; display:flex;
    align-items:baseline; gap:10px; flex-wrap:wrap; }}
  .a {{ margin-top:12px; padding-left:24px; }}
  .a p:first-child {{ margin-top:0; }} .a p:last-child {{ margin-bottom:0; }}
  .dot {{ width:9px; height:9px; border-radius:50%; flex:0 0 9px; display:inline-block; }}
  .dot.b {{ background:var(--teal); }} .dot.a {{ background:var(--amber); }}
  .dot.r {{ background:var(--red); }}
  .tag {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
    font-weight:800; padding:3px 9px; border-radius:999px; margin-left:auto; }}
  .tag.b {{ background:#e3f4f1; color:var(--teal); }}
  .tag.a {{ background:#fdf1e0; color:var(--amber); }}
  .tag.r {{ background:#fdeaec; color:var(--red); }}

  .kicker-stat {{ font-size:56px; font-weight:800; letter-spacing:-.045em;
    color:var(--red); line-height:1; margin:6px 0 8px; }}
  .stat-label {{ font-size:16px; max-width:60ch; }}

  .warn {{ border-left:5px solid var(--red); background:#fff; padding:15px 20px;
    border-radius:0 10px 10px 0; margin:16px 0; font-size:15.5px; }}
  blockquote {{ border-left:4px solid var(--ink); margin:14px 0; padding:2px 0 2px 18px;
    font-size:17px; font-weight:600; }}

  table.mini {{ width:100%; border-collapse:collapse; font-size:14.5px; margin:14px 0;
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    overflow:hidden; }}
  table.mini th, table.mini td {{ padding:9px 13px; text-align:left;
    border-bottom:1px solid var(--line); }}
  table.mini th {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em;
    color:var(--muted); background:#f2f4f7; }}
  table.mini tr:last-child td {{ border-bottom:none; }}
  table.mini tr.ours td {{ background:#e3f4f1; }}

  figure {{ margin:24px 0; background:var(--card); border:1px solid var(--line);
    border-radius:14px; padding:14px; }}
  figure img {{ width:100%; display:block; }}
  figcaption {{ font-size:13.5px; color:var(--muted); margin-top:10px; }}

  .todo {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    overflow:hidden; }}
  .todo div.row {{ display:flex; gap:14px; align-items:baseline; padding:14px 20px;
    border-bottom:1px solid var(--line); }}
  .todo div.row:last-child {{ border-bottom:none; }}
  .todo .n {{ font-weight:800; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .todo .txt {{ font-weight:600; }}
  .todo .why {{ color:var(--muted); font-size:14px; }}

  .foot {{ margin-top:54px; padding-top:20px; border-top:1px solid var(--line);
    font-size:13px; color:var(--muted); }}
  @media print {{
    header {{ background:#fff; color:var(--ink); }}
    header .kicker, header h1 {{ color:var(--red); }}
    header .q, header .meta {{ color:var(--muted); }}
    section, .qa, figure, table {{ page-break-inside:avoid; }}
  }}
</style>
</head>
<body>

<header>
  <div class="wrap">
    <div class="kicker">Team 07 · SDG 7 — Affordable and Clean Energy</div>
    <h1>Where we stand on the brief</h1>
    <p class="q">How might we make clean, affordable energy the default, not the
      exception?</p>
    <p class="meta">All 20 questions from the five stages, answered or marked as open —
       and the one finding our data produced that we did not go looking for.</p>
  </div>
</header>

<div class="wrap">

<div class="scorecards">
  <div class="sc s1"><div class="t">Feasibility</div>
    <div class="v">Our strongest card</div>
    <div class="d">Working, tested code. 57 passing tests. Runs offline on a Raspberry Pi.
      A finished JSON contract.</div></div>
  <div class="sc s2"><div class="t">Innovativeness</div>
    <div class="v">Good, under-explained</div>
    <div class="d">The idea is genuinely different — but we have never said what it is
      different <em>from</em>.</div></div>
  <div class="sc s3"><div class="t">Potential impact</div>
    <div class="v">Our weakest card</div>
    <div class="d">We have 655 million people. We do not have one named person or one
      named place.</div></div>
</div>

<div class="tally">
  <div class="b">{n_ans} answered</div>
  <div class="a">{n_par} partial</div>
  <div class="r">{n_open} open</div>
</div>

<p class="small" style="margin-top:22px; max-width:74ch">
  <strong>Read this first.</strong> The scoring weights all three criteria equally. Our
  strongest card is our weakest story, and our weakest card is the one the brief probes
  first. That gap is the whole agenda.</p>

<h2 style="margin-top:44px">The finding we did not go looking for</h2>
<p>We set out to describe the problem. The data handed us something sharper:</p>
<figure><img src="{FIG_DIVORCE}" alt="Sub-Saharan Africa compared with the rest of the world">
  <figcaption>Every country outside Sub-Saharan Africa, combined, against Sub-Saharan
    Africa alone. Same data, same years.</figcaption></figure>
<p>The world cut its access deficit in half between 2000 and 2024. But
   <strong>everywhere outside Sub-Saharan Africa the number fell
   {S['rest_cut_pct']:.0f}%</strong> — while <strong>inside it, the number rose
   {S['ssa_change']:.0f}%</strong>. Sub-Saharan Africa's share of the world's problem went
   from {S['ssa_share_then']:.1f}% to <strong>{S['ssa_share_2024_pct']}%</strong>.</p>
<p>And in {S['countries_worse_2010_2024']} countries the number is <em>higher</em> today
   than in 2010:</p>
<figure><img src="{FIG_BACKWARDS}" alt="Countries where the number grew 2010 to 2024">
  <figcaption>Countries where more people lack electricity in 2024 than in 2010.</figcaption></figure>
<p>This is what it looks like when population grows faster than the grid. It is also,
   bluntly, our market: the remaining {S['sum_countries_2024']/1e6:.0f} million people are
   not a global problem any more — they are a regional one, in countries where the
   supply is losing a race it is not currently running fast enough to win.</p>

{body}

<section>
  <h2>Where we should do this <span class="sub">· the decision we had never written down</span></h2>
  {RECOMMENDATION}
</section>

<section>
  <h2>Next actions, in order</h2>
  <div class="todo">
    {"".join(f'''<div class="row"><span class="n">{i}</span><span><span class="txt">{t}</span><br><span class="why">{w}</span></span></div>''' for i, (t, w, _) in enumerate(NEXT, 1))}
  </div>
</section>

<div class="foot">
  Companion to <code>data/eda_insights/dashboard.html</code> (the data) and
  <code>data/hackathon/status.md</code> (this analysis in markdown).<br>
  Rebuild: <code>python3 data/hackathon/build_brief.py</code>
</div>

</div>
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
print(f"  {n_ans} answered · {n_par} partial · {n_open} open")
