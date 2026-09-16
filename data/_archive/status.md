# Where we stand against the hackathon brief

An honest audit: for each question, what we can already answer, and what is
still missing. Written to be read before the pitch, not after.

Legend: **ANSWERED** · **PARTIAL** · **OPEN** — the last two have an action.

---

## Scorecard at a glance

| Criterion | Our position | Why |
|---|---|---|
| **Feasibility** | **Strongest** | Working, tested code. 57 passing tests. Runs offline on a Raspberry Pi. JSON contract exists. |
| **Innovativeness** | **Good, under-explained** | The idea is genuinely different, but we have not said what it is different *from*. |
| **Potential Impact** | **Weakest** | We have the top of the funnel (655 M people). We do not have a named person or a named place. |

The scoring rewards all three equally. Our strongest card is our weakest story,
and our weakest card is the one the brief probes first.

---

## Stage 1 · Get a Closer Look

### Who exactly is affected — a real person, not just "people"? — **OPEN**

This is the most important gap in the project.

What we have:

- A country-level count: 655 233 852 people without electricity (2024).
- A named concentration: 88.1 % of them in Sub-Saharan Africa; Nigeria first
  with 87 254 810.
- A **synthetic** persona in the simulator fixture: a clinic with a vaccine cold
  chain, and a household carrying home dialysis. Both are invented.

What is missing: a real facility, in a real place, with a real name.

Why it matters: the brief says "a real person, not just *people*" — and it is the
first question. Our entire dataset cannot answer it, because it does not go below
country level. We documented that limitation honestly; we now have to close it.

**Action.** Three sources, in order of cost:
1. `report.napocor.gov.ph/spugdb/` — NPC–SPUG metered generation per off-grid
   area. Login required, but it names the areas.
2. `napocor.gov.ph/spug-luzon-palawan-area/` — lists diesel plants by
   municipality and island. Public, readable.
3. DOH facility lists / barangay records — the health unit with the cold chain.

We need **one** named rural health unit in **one** named off-grid area. That is
the whole deliverable. It converts "655 million people" into "this clinic, this
island, this vaccine fridge".

### What's already been tried, and why hasn't it worked? — **PARTIAL**

What we have (from the data, not from opinion):

- The world *did* solve most of it: the deficit halved, 1.33 bn → 655 m.
- Outside Sub-Saharan Africa it fell 90.7 %. Inside, it rose 14.5 %.
- 21 countries went backwards between 2010 and 2024, adding 60.4 m people.
- At Sub-Saharan Africa's recent rate, halving the region's number takes
  **334 years**. The goal is six.

That is a strong factual answer to *what* has failed. It is not yet an answer to
*why*. The data shows population outrunning the grid; it does not show the
mechanism.

**Action.** One page on why grid extension stalled — cost per km, terrain, the
NPC–SPUG diesel subsidy structure, and why household solar (PAYG) has not
protected clinics: because PAYG sells to *households*, and a vaccine fridge is
nobody's customer.

### What part of this can we realistically tackle today? — **ANSWERED**

Strong, and demonstrable in the room:

- `allocator/` — a pure function, no I/O, no clock, no state, stdlib only.
- 57 automated tests proving the invariants (critical load cannot be displaced
  by comfort; nobody on a tier can starve another; credits cannot buy past a
  critical load).
- 60 properties in 5.8 ms, 500 in 43.7 ms. Runs offline on a Raspberry Pi.
- A completed JSON contract for a dashboard, and a live dashboard.

We can say: *this part is already built.*

---

## Stage 2 · Generate Ideas

### What's the boring, expected answer — and how do we beat it? — **ANSWERED**

The expected answers are all the same shape: **make more energy, or cap how much
each person takes.**

- More panels, a bigger battery.
- A quota per household.
- A prepaid meter.
- A priority list of *who* matters.

All four allocate by **how much**. We allocate by **what cannot wait** — and the
tier sits on the *load*, never on the building. That is the difference, and it is
provable rather than asserted: our policy delivers 89.9 % of critical load, where
equal-per-property delivers 33.2 % and first-come-first-served 49.8 %, on
identical weather and identical battery.

### No limits: what would we build? Now, the smallest version? — **ANSWERED**

- **No limits:** every off-grid microgrid on earth deciding by need rather than
  by whoever draws hardest.
- **Smallest version:** one relay per tier. A decision that currently ends as
  "denied 0.4 kWh" becomes "circuit 3 opened". That is the smallest thing that
  is still the real thing — and the algorithm already emits the decision.

### Is there an idea from elsewhere we could borrow and adapt? — **PARTIAL**

Borrowed already, but never said out loud:

- **Emergency triage** — sort by what happens if you wait, not by how sick
  someone sounds.
- **Weighted fair queuing** in networking — the same maths, applied to packets.
- **Progressive water-filling** — the fairness algorithm itself.

**Action.** Say this in the pitch. It costs one sentence and buys credibility:
the method is not invented from nothing, it is the same principle medicine and
networking already use, applied to energy.

### Which idea would actually surprise the jury? — **ANSWERED**

**Life and health is 5.5 % of the village's energy. Comfort is 46 %.**

The entire argument about allocation is about the 46 % that is air conditioning
and televisions. Protecting everything that saves lives costs almost nothing.
What costs is being willing to say no to comfort — and every baseline in our
comparison refuses to.

### App, platform, service, tool, or business model — which is this? — **OPEN**

We have never answered this, and the brief asks it directly.

Right now we are closest to **a tool** (a library with an API) that enables a
**service**. The honest answer is probably: a *component* — the decision layer
that other people's hardware and other people's business models sit on top of.

**Action.** Pick one and defend it in one sentence. If we cannot, the jury will
conclude we do not know what we built. My recommendation: **a tool**, sold or
donated as the decision layer, because that is what the code actually is — and
because claiming to be a business model we have not built is a losing answer.

---

## Stage 3 · Stress-Test Feasibility

### What do we need to build a rough version of this today? — **ANSWERED**

Nothing. It is built. This is the strongest answer we have.

### What's our riskiest assumption — how do we test it today? — **ANSWERED**

The riskiest assumption is **not technical**. It is behavioural:

> That a village will accept, and keep, a tier table that says no to air
> conditioning.

Everything downstream depends on it. The tier table is the only subjective input
in the whole method, and if it is not accepted and stable, the algorithm is
executing a table nobody agrees with.

Second-riskiest: that the behavioural model of voluntary curtailment (households
switching off comfort when the battery runs low) resembles real behaviour. The
simulation assumes it; reality needs a price signal or an agreement.

**How to test it today:** the tier table can be shown to anyone in ten minutes.
Give five people the load list and ask them to place each load on a tier. If they
agree, the assumption holds. If they disagree, we have found the real problem —
and it is cheaper to find it now than after deployment.

### One more week: what would we build next? — **ANSWERED**

The hardware bridge: one relay per tier, driven by the existing JSON output.

### Who's best placed to build, and later demo, each part? — **OPEN**

Not answered anywhere. Needs a team decision, not analysis.

---

## Stage 4 · Define Impact

### If this worked, what changes for the people affected? — **ANSWERED**

The vaccine stays cold. Nobody is denied life-critical power while a television
in the next building keeps running. That is the whole change, and it is stated
in the dashboard as a guarantee that is tested, not promised.

### How many people could this reach — and how would we know? — **PARTIAL**

We have the top of the funnel and it is solid:

- 655 233 852 people without access in 2024.
- 88.1 % of them in Sub-Saharan Africa.
- Cross-checked: our derived world figure for 2023 (677 005 200) matches the
  World Bank indicator computed independently, to four significant figures.

What we do **not** have is the **addressable slice**: health facilities with a
cold chain, in off-grid areas. The dataset is country-level and cannot produce
it. Quoting 655 million as our reachable market would be dishonest and a jury
will catch it.

**Action.** Do not quote 655 million as our market. Quote it as the *problem*,
then name the addressable slice from the Stage 1 sources, even if it is small.
"We can name 40 clinics" beats "we can reach 655 million people".

### What would it take to work in another city or country? — **ANSWERED**

Better than we have claimed. The algorithm receives numbers and returns numbers.
It knows nothing about geography, currency, language or weather. **The only local
input is the tier table.** Moving to another country means rewriting one table —
not the code, not the tests, not the contract.

That is a genuinely strong answer and it is sitting unused.

### What's the one sentence we want the jury to remember? — **OPEN**

Needs a decision. Draft candidates, from the data:

1. *"The village doesn't have a shortage of energy. It has a shortage of order."*
2. *"You cannot run a clinic on a first-come-first-served tariff."*
3. *"5.5 % of the energy saves every life in the village. The argument is about the other 46 %."*

My recommendation is (3) — it is a number the jury can check, it is the actual
finding, and it is the one they will still remember afterwards.

---

## Stage 5 · Prep the Pitch

| Prompt | Status |
|---|---|
| Creativity: what's different, in one sentence? | **Needs decision** — see the one-sentence candidates above |
| Feasibility: can we show it, not just tell it? | **Yes** — live dashboard, live `python -m harness.cli`, 57 tests |
| Impact: who benefits, roughly how much? | **Needs the named facility** |
| Rehearsed under 4 minutes? | Not yet |

The pitch is three answers in order — Creativity, Feasibility, Impact — because
that is exactly what is scored. The dashboard is the Feasibility evidence and
should be *shown*, not described.

---

## What to do next, in order

1. **Name a facility.** One rural health unit, one off-grid area. Closes the
   first and loudest question, and gives Impact a number that is real.
2. **Pick the one sentence.** (3) is my recommendation.
3. **Answer "tool or business model".** One sentence, defensible.
4. **Write the "why it hasn't worked" page.** The data gives *what*; we need *why*.
5. **Say where the idea came from.** Triage, fair queuing, water-filling. One line.
6. **Rehearse to 4 minutes.** Three sections: what's different, show it, who benefits.
