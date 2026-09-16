# `data/eda_insights/` — what the electricity-access data says

**The deliverable is [`dashboard.html`](dashboard.html).** Open it in any browser.
One self-contained file, no dependencies, works offline. That is the page to show
people who have never seen the dataset.

---

## What is in the dashboard

Written for a first-time reader. Nine steps, no recommendations, every number traced
to the file.

| Step | What it covers |
|---|---|
| Before you read | What the dataset is, and four caveats that change how to read it |
| 1 | The headline number, 2000 vs 2024 |
| 2 | India — the proof that the number responds |
| 3 | The finding: the rest of the world −91%, Sub-Saharan Africa +14% |
| 4 | Where the 655 million live, with the top 20 as a table |
| 5 | Those same 20 countries split by direction of travel |
| 6 | The 21 countries going backwards |
| 7 | Where the arithmetic points for 2030 |
| 8 | The slices the data supports — and what would decide between them |
| 9 | Eight questions marked answered or not answered |

Step 8 is the one to read closely: it lays out four ways to slice the data, then lists
the criteria that are **not** in this file. The data does not choose a target.

---

## Layout

```
dashboard.html          ← the deliverable
README.md               this file
findings.md             the longer written analysis, same data

figures/                story_1..7, the charts used in the dashboard
                        (also IMG_4506/7/8.PNG, the original screenshots)
outputs/                the numbers as data files
  summary_metrics.json  data profile, corrected ranking, cross-checks
  story_metrics.json    the figures used by the dashboard
  corrected_top15.csv   top 15 with regional averages removed
  latest_per_country.csv
  global_timeseries.csv
  regional_breakdown.csv
  concentration.csv
  movers_2000_2024.csv
  movers_2010_2024.csv

scripts/
  build_dashboard.py        rebuilds dashboard.html + all figures
  fixed_analizing_need.py   corrected version of the original script
  02_eda_analysis.py        the wider exploratory analysis
  ocr.swift                 macOS Vision OCR (used to read the screenshots)
```

---

## Rebuild

```bash
python3 data/eda_insights/scripts/build_dashboard.py
```

Requires `pandas`, `numpy`, `matplotlib`. The script audits every figure at build
time: it measures the bounding box of each label and **fails loudly** if two labels
overlap, if a label leaves the plot area, or if a label sits on top of a data line.
It prints a per-figure report and a final verdict.

---

## Headline numbers

| | |
|---|---|
| People without electricity, 2024 | **655 233 852** |
| The same in 2000 | 1 329 068 818 |
| Change | **−50.7 %** |
| Sub-Saharan Africa's share, 2000 → 2024 | 37.7 % → **88.1 %** |
| Outside Sub-Saharan Africa, 2000 → 2024 | −90.7 % |
| Inside Sub-Saharan Africa | **+14.5 %** |
| Countries going backwards since 2010 | **21**, adding 60 400 538 people |
| Projected for 2030 at the recent pace | ≈ **508 772 098** |
| Top 20 countries' share of the world total | **77.9 %** |

---

## Scope — what this dataset can and cannot say

**Can:** how many people lack a connection, per country and year; the direction of
travel; where the remaining problem is concentrated; whether the 2030 goal is
reachable at the current pace.

**Cannot:** distinguish a connection from a *reliable* supply; anything below country
level; per-capita or access-rate figures (no population column); or the size of any
addressable group, since that depends on criteria the file does not contain.
