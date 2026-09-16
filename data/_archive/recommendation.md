# Where we should do this

Written down because this analysis previously existed only in conversation and would
have been lost. It answers the brief's first question — *"who exactly is affected"*.

Numbers come from `data/people-without-electricity-country.csv` via
`data/eda_insights/`. The judgement is mine and is marked as judgement.

---

## The bet

> **Sub-Saharan Africa — but not as a geography play. As a *load* play: the vaccine
> cold chain. Entering through East Africa.**

Not "Africa" as a market. Africa as the place where a specific load — a vaccine fridge
in a health unit — has no power, and where the algorithm's design is aimed.

---

## Three reasons

### 1. Where the problem is

Not a judgement call. Arithmetic from the dataset:

| | |
|---|---|
| Sub-Saharan Africa's share of the global access deficit | **88.1 %** (was 37.7 % in 2000) |
| Countries where the deficit grew 2010–2024 | **21**, of which **17 are in Africa** |
| People those countries added | **60.4 million** |
| Sub-Saharan Africa's own change 2000–2024 | **+14.5 %** |

The rest of the world cut its number by 90.7 % over the same period. The remaining
problem is not global any more.

### 2. Where the algorithm's story lands

This is the part that decides it, and it is not visible in the data.

The method's entire claim is that **life-critical load can never be displaced by
comfort**. In the Philippines that is an optimisation story. In Sub-Saharan Africa it
is: *the vaccine was ruined and a child was not immunised.*

Same code. Completely different stakes. And the second version is the one that opens
doors at Gavi, WHO and health ministries — where **the buyer already exists and already
has a budget**.

### 3. Where we can actually execute

**Kenya, Tanzania and Uganda** — roughly 68 million people combined.

- Anglophone, accessible procurement and legal environment.
- Functioning national cold-chain programmes.
- An off-the-shelf solar PAYG ecosystem: we do not have to build hardware, technicians
  and financing from zero.
- All three on a downward trend. We ride the current instead of fighting it.

---

## Why not the Philippines

It is the comfortable choice and I would resist it.

**What is genuinely good there:** verified data already in the repo, public
NPC–SPUG diesel costs (the strongest economic argument available anywhere), and a
real institutional buyer in NPC–SPUG / DOE / NEA.

**Why it still loses:** rural access is **97.6 %**, and the deficit fell from
20.1 million to 6.0 million between 2000 and 2024. The project's own headline figure —
2.3 million — is a **ceiling, not a runway**. You cannot build a growth story on a
market that is closing.

**Keep it, but demote it.** Not "market" but **reference deployment**: it de-risks the
demo, it supplies the diesel-cost benchmark for the economics slide, and it proves the
figures against an independent source. Just not the bet.

---

## The honest problem with this recommendation

The countries where the deficit is **growing** — DR Congo (+25 M), Niger, Chad, Malawi,
South Sudan, Mali — are exactly the countries where it is **hardest to deploy**.
East Africa is where it is **shrinking**.

There is a real tension between *biggest problem* and *deployable*, and I do not want to
hide it.

**Resolution:** prove it in East Africa, aim at Central and West Africa.

**And the caveat on my own advice:** if the team's real strength is field operations
rather than product engineering, this answer flips. Then DR Congo and Nigeria become
the prize despite being the hardest — because someone has to be there anyway.

---

## What to verify before committing

Three questions, three sources. Do not mix them up.

| Question | Why it matters | Source |
|---|---|---|
| Is there a health facility with a cold chain in the target area? | Creates the tier-1 load — the whole point of the method | DOH facility lists, barangay records |
| What does diesel cost per kWh there? | The strongest economic argument, and it is public | MEDP, ERC universal charge filings |
| Is the area off-grid, or connected-but-unreliable? | Decides whether islanded mode is even the right mode | NPC–SPUG area lists, distribution utility reports |

---

## The limitation that applies to all of it

**None of these three questions can be answered from our dataset.** It is country-level.

That is itself the finding, and it is worth saying out loud rather than hiding:

> The file can size the market. It cannot choose a village — and the village is what
> decides whether the project works.

Which is why the single highest-value next step is not more analysis. It is naming one
health unit in one off-grid area.
