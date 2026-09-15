# `data/hackathon/` — the answers, as images

**The deliverable is [`answers/`](answers/) — five images, one per stage of the
hackathon brief.** Open them, or drop them into the pitch deck.

| Image | Stage | Questions |
|---|---|---|
| [`answers/stage_1_closer_look.png`](answers/stage_1_closer_look.png) | Get a Closer Look | 3 |
| [`answers/stage_2_ideas.png`](answers/stage_2_ideas.png) | Generate Ideas | 5 |
| [`answers/stage_3_feasibility.png`](answers/stage_3_feasibility.png) | Stress-Test Feasibility | 4 |
| [`answers/stage_4_impact.png`](answers/stage_4_impact.png) | Define Impact | 4 |
| [`answers/stage_5_pitch.png`](answers/stage_5_pitch.png) | Prep the Pitch | 4 |

Each image is 1999 × 1125 (16:9), sized to be projected as-is.

---

## What the labels mean

Every question carries one of three labels, and the label is the point:

| Label | Meaning |
|---|---|
| **ANSWERED** (teal) | The repository already answers this, and the answer is checked at build time. |
| **PARTIAL** (amber) | The data answers part of it. The slide says which part is missing. |
| **NOT IN THE DATA** (red) | The dataset cannot reach this question at all. |

**Eight of the twenty questions are not fully answerable from this repository.**
Saying so is deliberate. The brief's first question — *"who exactly is affected, a
real person, not just people"* — is the one this dataset is structurally unable to
answer, because it stops at the country border. Claiming otherwise in front of a
jury is the fastest way to lose the room.

---

## Every number is re-derived, not quoted

The build script does not trust the prose in this repository. It:

1. reads the country counts from `data/eda_insights/outputs/*.json`;
2. **re-runs `harness.cli`** and parses the policy table itself;
3. **re-counts the tier split** by walking `harness/scenario.build_barangay()`;
4. fails loudly if any of that is missing or unparseable.

So a slide cannot drift away from the code. If the allocator changes, the images
change with it, or the build stops.

```
$ python3 data/hackathon/build_answer_slides.py
wrote data/hackathon/answers/stage_1_closer_look.png  (246 KB)
...
slide audit:
  stage_1_closer_look (scale 1.00): clean
  stage_2_ideas (scale 0.92): clean
  stage_3_feasibility (scale 1.00): clean
  stage_4_impact (scale 1.00): clean
  stage_5_pitch (scale 1.00): clean

RESULT: all slides clean
```

The layout is **measured before it is drawn** and scaled to fit, then audited for
overflow and off-figure text. The first attempt overflowed stage 2 and clipped a
line in stage 3; the audit caught both. That check is why the build can be trusted
to refuse rather than to ship a broken slide.

---

## Where the numbers come from

| Figure on the slides | Source |
|---|---|
| 655 233 852 without access, 2024 | `people-without-electricity-country.csv`, sum of 214 countries |
| 88.1 % Sub-Saharan Africa | World Bank regional aggregate `WB_SSA` ÷ `OWID_WRL` |
| 21 countries worse, +60 400 538 | derived in `story_metrics.json` |
| 333 years to halve the region | extrapolation of the region's own 2010–2024 pace |
| 89.85 / 33.22 / 49.75 / 53.83 % | `harness.cli --days 3 --sample`, re-run at build time |
| 5.5 % life and health, 46.0 % comfort | counted from `harness/scenario.py`, not quoted |
| 57 tests | `python3 -m pytest -q` |

---

## Related, and archived

`data/_archive/` holds the working documents this folder was built on, kept for the
reasoning rather than the output:

- `hackathon_questions.md` — the 21 questions, transcribed from the team's screenshots
- `status.md` — the honest per-question audit (ANSWERED / PARTIAL / OPEN)
- `recommendation.md` — where to deploy, and why not the Philippines
- `build_brief.py` — an earlier HTML version of these answers

Those are kept, not maintained. **This folder is the current answer.**
