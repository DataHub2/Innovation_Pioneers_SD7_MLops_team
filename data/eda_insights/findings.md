# EDA — `people-without-electricity-country.csv`

**Source file:** `data/people-without-electricity-country.csv`
**Analysis script:** `scripts/02_eda_analysis.py` (reproducible, run from repo root)
**Raw outputs:** `outputs/` · **Figures:** `figures/`

Everything below is computed from the file itself. Numbers in `outputs/summary_metrics.json`.

---

## 1. What the dataset actually is

| Property | Value |
|---|---|
| Rows | 7 140 |
| Entities | 229 — of which **214 are countries**, 15 are aggregates |
| Period | 1990 – 2024 (35 years, annual) |
| Columns | `Entity`, `Code`, `Year`, `Number of people without access to electricity` |
| Null cells | **0** |
| Negative values | **0** |
| Zero values | 2 950 (41.3 % of all rows) |

Two structural facts decide how everything else must be read.

**The zeros are data, not missing values.** There are no nulls anywhere in the file. A zero
means "effectively nobody without access". **49 entities are zero in every single year** —
Germany, Japan, France, Australia, Canada and so on. Any EDA that drops or imputes zeros
would invent a problem that the file says does not exist.

**The panel is unbalanced at the start, and that creates a fake trend.** Coverage grows from
102 entities in 1990 to 224 in 2000 and 228 in 2024:

| Year | Entities reporting |
|---|---|
| 1990 | 102 |
| 1995 | 152 |
| 2000 | 224 |
| 2024 | 228 |

So the global total genuinely appears to *rise* from 119 M (1990) to 1 329 M (2000). That is
almost entirely new countries entering the panel, not electrification going backwards. **The
global series is only usable from 2000 onward.** This is exactly the artefact shaded in
`figures/fig1_global_trajectory.png`.

**Only Kosovo has stale data** (last point 1999). Every other country reaches 2024, so mixing
years inside a ranking is *not* a real problem here — but the original script could not tell
you that, which is why the corrected version prints the year column.

---

## 2. Bug in `data_tracing/analizing_need.py`

The script intends to "filter out regional aggregates and non-country entities". It does not.

```python
clean_df = df[df['Code'].notna() & ~df['Code'].str.startswith('OWID')].copy()
```

* `df['Code'].notna()` is a **no-op** — the `Code` column has zero nulls.
* `~startswith('OWID')` catches the 8 `OWID_*` entities but **misses the seven `WB_*` ones**:
  `WB_SSA`, `WB_EAP`, `WB_ECA`, `WB_LAC`, `WB_MENAP`, `WB_NA`, `WB_SA`.

Three aggregates therefore survive into the top 15 — Sub-Saharan Africa (WB) at **rank 1**,
East Asia and Pacific (WB) at rank 5, and MENAP (WB) at rank 7.

| | Top-15 total | First place |
|---|---|---|
| Original script | **1 055 304 276** | Sub-Saharan Africa (WB) — 579 M |
| Corrected | **456 507 645** | Nigeria — 87 M |
| Error | **+131.2 %** | an entire region reported as if it were a country |

Roughly **600 million people are double-counted** — the region and its member states both
appear. See `figures/fig3_top15_corrected.png` and `outputs/corrected_top15.csv`.
A fixed script is provided at `scripts/fixed_analizing_need.py`.

**Caveat on the fix.** Excluding all `OWID_*` also drops Kosovo and the Channel Islands,
which are real places. Both are zero in every year they appear, so excluding them changes no
ranking — but the principled filter is "aggregate or not", not "OWID prefix or not".

---

## 3. The headline story: the problem is moving into Africa

The world halved its access deficit between 2000 and 2024 — from about **1.33 billion to
655 million** (sum of countries; the `World` aggregate says 657 M). The regional split of
what remains has completely inverted.

| Region | 2024 deficit | Share of world |
|---|---|---|
| **Sub-Saharan Africa** | **579 M** | **88.1 %** |
| East Asia and Pacific | 34.4 M | 5.2 % |
| MENAP | 26.2 M | 4.0 % |
| Latin America & Caribbean | 12.9 M | 2.0 % |
| South Asia | 2.9 M | 0.4 % |
| Europe & Central Asia | 0.01 M | ~0 % |
| North America | 0 M | 0 % |

Sub-Saharan Africa's share went from **37.7 % in 2000 to 88.1 % in 2024**. In absolute terms
its deficit barely moved (506 M → 579 M) while the rest of the world collapsed.

> The world's electrification problem is no longer global. It is African, and it is
> concentrated in a handful of countries.

---

## 4. Concentration is falling — the problem is spreading

| Year | Largest country | Top 5 | Top 10 | Top 20 | HHI | Gini |
|---|---|---|---|---|---|---|
| 2000 | 31.6 % | 51.9 % | 64.7 % | — | 0.1173 | 0.887 |
| 2010 | 25.5 % | 49.9 % | 63.0 % | — | 0.0875 | 0.886 |
| 2024 | **13.3 %** | 43.4 % | 58.2 % | 77.7 % | **0.0560** | 0.889 |

In 2000 one country (India) held a third of the global deficit. In 2024 no country holds more
than 13 %. HHI more than halved.

Note the Gini stays flat at ~0.889. The two measures disagree because they answer different
questions: HHI is about *mass* in the largest units, Gini about *inequality across all* 214
units — and the long tail of zeros is unchanged. **HHI is the right measure here**; a flat
Gini would wrongly suggest nothing changed.

Practical reading: there is no longer a single country whose progress determines the SDG.
Twenty countries now cover 78 % of the deficit.

---

## 5. Successes and reversals

**Five countries that solved it** (2000 → 2024, absolute):

| Country | 2000 | 2024 | Change |
|---|---|---|---|
| India | 420.0 M | 1.5 M | **−418.5 M** |
| Bangladesh | 91.5 M | 0.9 M | −90.6 M |
| China | 41.7 M | 0 | −41.7 M |
| Pakistan | 42.1 M | 10.8 M | −31.3 M |
| Indonesia | 29.6 M | 0.3 M | −29.3 M |

**75 entities reached zero** from a positive start — including China, Vietnam, Iran, Egypt,
Iraq, Algeria and Bhutan.

**Five countries went backwards over the same period:**

| Country | 2000 | 2024 | Change |
|---|---|---|---|
| DR Congo | 47.1 M | 84.7 M | **+37.6 M** |
| Nigeria | 71.8 M | 87.3 M | +15.5 M |
| Niger | 10.8 M | 21.3 M | +10.5 M |
| Chad | 8.2 M | 17.6 M | +9.3 M |
| Malawi | 10.8 M | 18.3 M | +7.5 M |

**21 countries got worse between 2010 and 2024**, while the world deficit was falling 4 % per
year. Together they added **60.4 million** people. This is the group where population growth
outran electrification. DR Congo and Nigeria between them account for two thirds of it —
and they are also ranks 1 and 2 in the corrected top 15. See `figures/fig5_movers.png`.

---

## 6. Pace and the 2030 outlook

| Period | Annual change in global deficit |
|---|---|
| 2000 → 2010 | −1.40 % / year |
| 2010 → 2024 | **−3.97 % / year** |

Progress accelerated roughly threefold. Extrapolating the 2010–2024 pace forward:

> **≈ 509 million people would still lack access in 2030.**

SDG 7.1 calls for universal access by 2030. Even at the *recent, accelerated* rate the gap
closes by only about 150 M in six years. **The target is not reachable by extrapolation of the
current trend.** This is the single strongest quantitative argument in the file for the
project the repository describes.

Caveat: this is a log-linear extrapolation of an aggregate, not a country-level model. It
assumes every country holds its recent pace — optimistic, since the 21 worsening countries
are exactly the ones where that assumption is least likely to hold.

---

## 7. Cross-check against `docs/METHOD.md` §8

The repository's pitch quotes externally-sourced scale figures. This file reproduces them
exactly:

| Figure | METHOD.md claims | This CSV (2023) | Match |
|---|---|---|---|
| World without access | ≈ 677 M | **677 005 200** | exact |
| Philippines without access | ≈ 2.3 M | **2 297 824** | exact |

METHOD.md derived those by multiplying World Bank population by `(1 − access rate)` from a
*different* indicator (`EG.ELC.ACCS.ZS`). This CSV is an independent count of the same
quantity, and the two agree to four significant figures. That is a genuine validation of the
pitch arithmetic, and it is worth stating explicitly: the derived figure and the directly
measured figure are the same number.

Two things this does **not** fix, both of which METHOD.md already flags:

1. The file counts **connections**, not reliable supply. Brownouts and diesel backup are
   invisible here. The addressable set for the allocator is therefore larger than 677 M —
   but it is not measured by this dataset, and no number should be quoted for it.
2. The allocator's tier shares (5.5 % life-critical, 46 % comfort) come from the simulator
   fixture, **not** from this file. Nothing here validates those.

---

## 8. Limitations of this analysis

* **No population or access-rate column**, so no per-capita or percentage view is possible
  from this file alone. Only absolute counts.
* **No sub-national detail.** Everything is country-level; the allocator targets barangays
  and villages, which are far below this resolution. This file cannot select a site.
* **A few values carry decimals** (e.g. India 2024 = 1 450 913.8), indicating the World Bank
  interpolates. Treated as exact here; they are not.
* **The 1990–1999 panel is incomplete**, so no trend before 2000 should be quoted.
* **Aggregate rows are internally inconsistent** with member states by ~2 M in 2024
  (regional sum 655.6 M vs World 657.3 M) — a rounding/coverage artefact of the source, not
  of this analysis.
* Projections are extrapolations, not forecasts.

---

## 9. What this means for the repository

1. **Fix the script.** `data_tracing/analizing_need.py` states an intent it does not
   implement; the fix is one line (`startswith(('OWID_', 'WB_'))`). A corrected copy is in
   `scripts/fixed_analizing_need.py`.
2. **The geography argument is now backed by data.** METHOD.md §8.3 says site selection has
   not been done and must not be read into the SPUG page examples. This file supports
   narrowing the *search space* to Sub-Saharan Africa on evidence — 88 % of the deficit, and
   21 countries going backwards. It still does **not** identify a village, and should not be
   presented as if it did.
3. **The strongest pitch line is now quantitative:** *at the current rate, ~509 M people are
   still without access in 2030 — the target is missed by a wide margin, and the remaining
   deficit is concentrated in countries where population is outrunning the grid.*
4. **Do not carry these numbers into the allocator's tier shares.** Country counts size the
   market; they say nothing about the 5.5 % / 46 % split, which remains a fixture assumption.
