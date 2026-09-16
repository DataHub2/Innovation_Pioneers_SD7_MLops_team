# How we allocate the energy — method, evidence and limitations

This document describes the algorithm, why it looks the way it does, what it
achieves in simulation, and exactly which of its numbers are assumptions.
It is written to be readable on its own, without any knowledge of the code.

---

## 1. The problem

A village solar installation does not deliver unlimited energy. Someone has to
decide who gets it when it is not enough for everyone. Get that wrong and it
fails in one of two ways:

* Whoever draws the most, or plugs in first, gets the most. A two-person flat
  with air conditioning can then push out a vaccine cold chain.
* Whoever shouts loudest gets the most. Everyone declares that they need
  everything.

Both failures share a root cause: allocating by **how much** someone wants.
That is the wrong measure.

## 2. The core insight: need is not measured in kWh

A clinic consumes surprisingly **little** electricity. A vaccine cold chain,
dialysis, emergency lighting and medical device charging in a small rural health
unit often add up to less than two kWh per day. A household with air
conditioning, a freezer and a TV draws several times that.

So in raw kWh terms, the household is "bigger" than the clinic. An algorithm
that allocates by quantity gives the air conditioner more than the vaccine
fridge — which is exactly backwards.

What actually separates them are two other things:

| Question | Why it decides the outcome |
|---|---|
| **What happens if the load is not served?** | The vaccine is ruined, the patient is harmed. It cannot be undone. |
| **Can the load wait?** | Air conditioning can be off for two hours. Rice can be cooked tomorrow. Water can be pumped at noon instead of 7 pm. |

The second question matters especially for solar, because the sun delivers
intermittent power. A load that can move in time can consume **surplus** instead
of competing for scarce energy.

**The conclusion: allocation is not about how much, but about what cannot wait.**

## 3. The method: a load ladder, not a weight table

Need is broken down into individual **loads**, and every load is placed on a
tier of a ladder:

| Tier | What it is | Can it wait? | Examples |
|---|---|---|---|
| **1** | Life and health | Never | vaccine cold chain, dialysis, drinking water pump, emergency lighting, medical devices |
| **2** | Basic need | An hour or so | lighting, phone charging, food fridge, fan |
| **3** | Productive | Yes, to solar hours | ice maker, shop fridge, sewing machine, irrigation |
| **4** | Comfort | Yes | air conditioning, TV, extra freezer, leisure charging |

The algorithm is then three steps:

1. **Fill the tiers from the bottom up.** Tier 1 first, then 2, 3, 4. Energy runs
   out somewhere in the ladder, and everything above that line is off — no
   matter who is asking.
2. **On each tier: non-shiftable loads first, shiftable loads from surplus.**
   Shiftable loads run when the sun delivers more than the village needs right
   now. A shiftable load past its deadline is treated as non-shiftable, so the
   water tank really is full by evening.
3. **Within each group: weighted max-min fairness.** The budget is shared so
   that whoever needs little is served first, and the rest is shared in
   proportion. Nobody receives zero while someone else receives more than they
   need. This is what stops two households on the same tier from starving each
   other.

## 4. This is why a household can never take energy from the clinic

The tier sits on the **load**, not on the building.

* A clinic can have both a tier-1 load (vaccine cold chain) and a tier-4 load
  (air conditioning in the waiting room).
* A household can have a tier-1 load (home dialysis) and a tier-4 load (TV).

The algorithm therefore never needs to know what a building *is*, and it cannot
be gamed by calling yourself a hospital. Whoever carries a critical load has
that critical load protected. The two-person household with air conditioning
never competes with the vaccine fridge, because they sit on different tiers.

> **There is exactly one subjective choice in the whole method:** which load sits
> on which tier. That choice is made by the village, openly, in a table that can
> be changed. The algorithm encodes no morality — it executes a table that
> people drew up.

## 5. The reserve rule: comfort must not drink the battery

One downside of simply filling the ladder from the bottom is that comfort can
drain the battery during a sunny day, leaving the village dark when the critical
load is needed at night. That failure showed up in simulation and was fixed:

* Tier 3 may only draw on stored energy while the battery is above 25 %.
* Tier 4 may only draw on stored energy while the battery is above 50 %.
* Tiers 1 and 2 may always draw on the battery.

The effect is visible in the numbers below: comfort switches off in the evening
and the critical load survives.

## 6. Credits: voluntary curtailment instead of policing

A household that wants more can declare more. The system defends itself in three
ways:

* **Declaration check.** A declaration above three times the historical daily
  requirement is scaled down automatically.
* **The ladder.** A household can only binge within its own tier. That damages
  its own comfort, never anyone else's need.
* **Credits.** A household that voluntarily switches off its comfort during a
  scarcity cycle earns credits. Credits give a **bounded** advantage (at most
  +50 %) within that household's own tier, never on tier 1, and they decay
  slowly.

> **Nobody can buy their way past a critical load.** Credits are a bounded
> reciprocity term, not a currency.

The reward is only paid out when there is genuine scarcity. Otherwise it would
pay to switch off for no reason just to farm credits.

## 7. Results

The same village, the same weather, the same battery — only a different
allocation. Three days, 15-minute steps, 31 properties, 20 kWp solar, 80 kWh
battery.

**Normal weather (cloud 1.0 / 0.7 / 0.4):**

| Policy | Critical power delivered | Life+basic | Comfort | Unserved critical load | Cycles without critical power |
|---|---|---|---|---|---|
| **Load ladder (ours)** | **89.9 %** | 94.2 % | 29.6 % | **9.2 kWh** | 17 |
| Equal per property | 33.2 % | 67.2 % | 50.1 % | 64.4 kWh | 116 |
| First come, first served | 49.8 % | 68.6 % | 60.4 % | 54.2 kWh | 121 |
| Max-min without a ladder | 53.8 % | 70.2 % | 58.8 % | 50.6 kWh | 91 |

**Sunny days:** critical power 95.8 % against 39.3 % for "equal per property".
**Four very cloudy days:** critical power 73.2 % against 24.0 %.

The pattern holds in every weather: **our algorithm sacrifices comfort to
protect critical load. The baselines do the opposite.** That is the whole
difference, and it is measurable.

Note also that "equal per property" has the lowest Gini coefficient (0.26) — it
is the most *equal* — and at the same time the worst critical power delivery.
That is why equality in kWh is not the same thing as reasonableness.

### The key figure

| Tier | Share of the village's total demand |
|---|---|
| 1 — life and health | **5.5 %** |
| 2 — basic need | 34.6 % |
| 3 — productive | 13.8 % |
| 4 — comfort | **46.0 %** |

Everything life-critical in the village is **5.5 % of the energy**. The argument
about allocation is in practice about the 46 % that is comfort. Protecting what
saves lives costs almost nothing — what costs is daring to say no to air
conditioning.

> It is not the shortage that takes lives. It is the order in which we allocate.

## 8. Real-world data: what we use, and what we still assume

### 8.1 Verified figures (external, public sources)

These are the only figures in this project that do **not** come from our fixture.
They are the scale case, pulled live from the World Bank open API (indicator
`EG.ELC.ACCS.ZS`, the SDG 7.1.1 dataset compiled by ESMAP, `lastupdated`
2026-07-13):

| Indicator | Value | Year |
|---|---|---|
| Access to electricity, Philippines (`EG.ELC.ACCS.ZS`, PH) | 98.0 % | 2023 |
| Access to electricity, rural Philippines (`EG.ELC.ACCS.RU.ZS`) | 97.6 % | 2023 |
| Population, Philippines (`SP.POP.TOTL`) | 114,891,199 | 2023 |
| Access to electricity, world (`EG.ELC.ACCS.ZS`, WLD) | 91.60 % | 2023 |
| Population, world (`SP.POP.TOTL`, WLD) | 8,062,923,417 | 2023 |

Reproduce with:

```
https://api.worldbank.org/v2/country/PH/indicator/EG.ELC.ACCS.ZS?format=json&date=2015:2023
https://api.worldbank.org/v2/country/PH/indicator/EG.ELC.ACCS.RU.ZS?format=json&date=2015:2023
https://api.worldbank.org/v2/country/PH/indicator/SP.POP.TOTL?format=json&date=2020:2023
https://api.worldbank.org/v2/country/WLD/indicator/EG.ELC.ACCS.ZS?format=json&date=2019:2023
https://api.worldbank.org/v2/country/WLD/indicator/SP.POP.TOTL?format=json&date=2023
```

### 8.2 How many could this reach?

Derived from those figures, with the arithmetic shown so it can be checked:

| Scope | People without access | How it is computed |
|---|---|---|
| Philippines, 2023 | **≈ 2.3 million** | 114,891,199 × (1 − 0.980) |
| World, 2023 | **≈ 677 million** | 8,062,923,417 × (1 − 0.916) |

Two honest qualifications, and they matter more than the headline number:

1. **"Access" is not "reliable access".** The World Bank indicator measures
   whether a household is connected, not whether the supply is steady. In the
   Philippines a connection frequently means brownouts, typhoon outages and
   diesel backup. Our algorithm is useful for exactly those connected-but-unreliable
   places, which are far more numerous than the 2 % without any connection.
   The addressable set is therefore larger than 2.3 million, but that set is not
   measured by this indicator, and we do not claim a number for it.
2. **Philippine household electrification is reported differently by different
   agencies.** The Department of Energy (DOE) reports household electrification
   levels and a count of unenergised barangays that do not match the World Bank
   percentage, because the definitions of "energised" differ. We have **not**
   verified the DOE figure from a primary source, so we do not quote one. That
   number has to be pulled from DOE before it goes in a pitch.

### 8.3 Which places, and how much they need — the sourcing chain

This is the part that decides whether the pitch survives a follow-up question.
Three separate questions need three separate sources, and they must not be mixed
up.

**Question 1: which places genuinely lack reliable supply?**

**We have not answered this question. We have only located where it can be
answered.** No ranking of candidate sites has been done, and nothing in this
document should be read as one. What follows is the method and the sources, with
an explicit verification status for each, so that the claim can be checked
rather than trusted.

The authoritative list is not a map or a report — it is the set of areas where
the state still runs diesel plants because the grid never arrived. The National
Power Corporation (NPC), through its Small Power Utilities Group (SPUG), is
mandated to electrify exactly those areas.

| What we want | Where it comes from | Verification status |
|---|---|---|
| The number of missionary and off-grid areas, and how many NPC-SPUG serves | Missionary Electrification Development Plan 2024–2028, DOE: `prod-cms.doe.gov.ph/documents/d/guest/medp-2024-2028-pdf` | **Unverified.** A search index reports "276 of 294 areas, 279 power plants". We could not read the PDF (it returned as binary), so this figure is not confirmed and must not be quoted until someone opens the document |
| The names of the areas and their individual diesel plants | NPC area pages, e.g. `napocor.gov.ph/spug-luzon-palawan-area/` | **Partly verified.** The page exists and lists plants by municipality and island. We have not read all area pages, and listing in this set is not evidence of need level |
| Barangay-level electrification status | National Electrification Administration (NEA) | **Not published.** An FOI request for exactly this dataset was filed at `foi.gov.ph/agencies/nea/`. That is the route to it |
| Metered generation and sales per area | NPC-SPUG Database Online Reporting System, `report.napocor.gov.ph/spugdb/` | **Verified to exist, login required.** This is where the actual demand numbers live |

> **Provenance note, stated plainly.** The Palawan examples earlier in this
> section came from the first SPUG area page to surface in a search, not from a
> needs assessment. Places such as Agutaya, Araceli, Balabac, Taytay, Cuyo and
> Coron are real and are real diesel plants, but they were not *chosen* — they
> happened to be on the page we could read. Presenting them as "the places that
> need it most" would be circular reasoning: we would be using the availability
> of a web page as a proxy for need.

**What selecting a site actually requires.** "Genuinely needed" has to be a
defined criterion before data is collected, or the choice becomes an accident.
The same discipline as the load ladder applies: fix the criterion, then let the
data decide. Candidate criteria, all of which are measurable from the sources
above:

| Criterion | Why it matters | Data source |
|---|---|---|
| Not connected to any grid | Removes the option of just importing power | DOE / NEA |
| Currently served by diesel generation | The status quo is expensive and fragile; solar competes directly | NPC-SPUG area lists |
| Cost of diesel power per kWh, and the subsidy per area | The strongest economic argument, and it is public | MEDP, ERC universal charge filings |
| Distance and difficulty of grid extension | Explains why the grid never arrived | NGCP transmission plans |
| Presence of a health facility with a cold chain | Creates a tier-1 load, which is the whole point of the ladder | DOH facility lists, barangay records |
| Households and population per area | Sizing, and scale of impact | PSA census, barangay registers |
| Frequency and duration of outages | Distinguishes "no supply" from "bad supply", which are different problems | Distribution utility reports, news reports |

A defensible shortlist is what comes out of applying those criteria to the full
set. We have not done that, and it is the single highest-value piece of research
left before the pitch.

**Question 2: how much energy does one of those places need?**

Do **not** use the fixture numbers from section 7 for this. Three usable
directions:

1. **The SPUG database** (`report.napocor.gov.ph/spugdb/`) records what each
   diesel plant actually generates and sells, per area. This is the strongest
   possible demand figure, because it is metered, but it needs login access.
2. **The Multi-Tier Framework (MTF)**, the World Bank / ESMAP standard for
   measuring energy access. It defines access levels by daily kWh and peak
   watts rather than by "connected or not". Landing page:
   `esmap.org/energy-solutions/multi-tier-framework-energy-access-mtf`. The
   numeric thresholds are in the ESMAP publication *Beyond Connections: Energy
   Access Redefined*. **We have not verified the threshold table against the
   live document**, so do not quote specific thresholds until someone opens it.
3. **PSA household data** and DOE household electrification reports, for
   households per barangay and appliances in use.

**Question 3: how much can one of those places generate?**

The supply side is the easiest to verify, because it is measured from satellites
and published for free:

* The Philippines receives **over 7 kWh/m²/day in April (peak month) and about
  3 kWh/m²/day in December (low month)**, based on observations across 33 cities
  (Malicdem 2015, cited in Wikipedia's *Electricity sector in the Philippines*).
* For a site-specific number, use **Global Solar Atlas** or **PVGIS** with the
  actual coordinates. Both are free and are the numbers a reviewer will accept.

**The fixture's own numbers are still placeholders.** Where each one has to be
replaced, and with what, is the table in section 8.4.

### 8.4 What is still an assumption

Everything in section 7 comes from a test fixture built so the algorithm could
be developed and measured before real data exists. Nothing in section 7 is
measured field data.

| Assumption | Realistic? | Must be replaced with |
|---|---|---|
| Solar irradiance: sine between 06:00 and 18:00, cloud factor per day | Simplified | PVGIS or NSRDB data for the actual site |
| Load profiles per property type | Invented, but plausible in magnitude | Metered data, or DOE / ESMAP figures for Filipino households |
| Vaccine cold chain 1.2 kWh/day | Plausible order of magnitude | WHO cold chain requirements and the actual equipment in local health units |
| Share of households with air conditioning, freezer, e-bike | Invented | Barangay register or a survey |
| Battery 80 kWh, 20 kWp | Plausible for a small village installation | Actual sizing |
| Households curtail comfort when the battery < 35 % between 17:00 and 22:00 | Simplified behavioural model | Observed behaviour, or a pricing mechanism with the same effect |

**What is not an assumption is the method's guarantees:** that critical load can
never be displaced by comfort, that nobody on the same tier can starve another,
and that nobody can buy their way past a critical load. These are invariants and
they are tested (`tests/`).

## 9. Limitations

* The algorithm is **stateless and runs per timestep**. It does not optimise
  across a whole day. The reserve rule is a simple heuristic; a model-predictive
  variant could save more battery by consulting the forecast.
* It does not model **per-load power spikes**. A real installation must handle a
  compressor starting.
* It does not handle **grid connection or export**. If the village is connected,
  further options appear (selling surplus, importing at night).
* It models a single village. Scaling to many villages is a question of resource
  planning, not of allocation — that is a different component.
* The behavioural model for voluntary curtailment is simplified. In reality it
  takes a pricing mechanism or an agreement to produce the same effect.

## 10. What is built

| File | What it does |
|---|---|
| `allocator/` | The algorithm itself. A pure function: no dependencies, no I/O, no clock. |
| `allocator/fairness.py` | Weighted max-min fairness (progressive water filling), `O(n log n)`. |
| `allocator/policy.py` | The load ladder, the reserve rule, credits, reason codes. |
| `allocator/baselines.py` | Three comparison policies, including "equal per property". |
| `harness/` | Test fixture and simulation. Owns battery physics, load profiles and accounting. |
| `tests/` | 57 tests: 10 invariants (I1–I10) and 13 stress scenarios (S1–S13). |
| `docs/ALLOCATION_CONTRACT.md` | The interface to dashboard, data pipeline and hardware. |

### Invariants proven in test

| # | Invariant |
|---|---|
| I1 | The sum of granted energy never exceeds the budget |
| I2 | The sum of granted power never exceeds available power |
| I3 | If life and basic need are physically coverable, they are covered |
| I4 | Credits can never go negative and cannot be farmed without scarcity |
| I5 | The same input gives exactly the same output, even at exactly equal scores |
| I6 | Every property gets exactly one decision with exactly one reason |
| I7 | Nobody receives more than they declared |
| I8 | Sustained denial is raised as a warning |
| I9 | Credit accounting is consistent |
| I10 | No NaN, no negative numbers, no silent overspend |

### Running it

```bash
python -m pytest -q                       # all 57 tests
python -m harness.cli --days 3 --sample   # compare against the baselines, show a cycle
python -m harness.cli --days 3 --json out.json   # JSON for a dashboard
```

Performance: 60 properties 5.8 ms, 500 properties 43.7 ms median per timestep.
It runs on a Raspberry Pi in a barangay, offline.

## 11. Next steps

1. Replace the fixture numbers with real data. The contract does not change —
   only the input does.
2. Connect the output to a dashboard. The JSON format already exists in
   `harness/report.py` and `_dump_cycle`.
3. Build the bridge to hardware: one relay per tier, so a decision goes from
   "denied 0.4 kWh" to "circuit 3 opened".
4. Let a real village set the tier table. That is the only parameter that has to
   be right, and it is not a technical question.
