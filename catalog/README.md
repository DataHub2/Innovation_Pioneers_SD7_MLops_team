# Real parts for Solar Builder

The app's demo catalogue is invented. This one is not — it is real solar panels,
inverters and a battery for a **Philippine home**, taken from open equipment
lists published by NREL and from manufacturer datasheets.

Standard library only. No API key. No scraping of shops.

```
catalog/build.py              downloads the lists, filters them, writes web/catalog.json
catalog/verify_contract.py    checks that file against the shape the app reads
catalog/listings.seed.json    prices and shops — blank until we have real quotes
catalog/contract/             the payload captured from the live app, used as the contract
catalog/.cache/               the downloaded lists (gitignored)
```

## Run it

```bash
python3 catalog/build.py --offline          # use the cached CEC list
python3 catalog/build.py                    # first run downloads it
python3 catalog/build.py --offline --seed   # also scaffold listings.seed.json
python3 catalog/verify_contract.py          # always do this before pushing
```

Every run prints what it kept and what it dropped:

```
panels           3,368   dropped 16,474 other makes, 1,837 small, 0 unusable
inverters            4   Deye SG04LP1-EU, 220/230 V
batteries            1   Deye RW-F10.2, 43.2-57.6 V
C1 Budget      6 panels  6 in series  1 battery
C2 Balanced   10 panels 10 in series  1 battery
C3 Backup     14 panels 10 in series  2 battery
suppliers        0
listings         0   (17 row(s) still blank, dropped)
```

## The contract

`web/catalog.json` has to match what the deployed `catalog` server function
returns. That payload was captured from `sun-plan-build.lovable.app` and is kept
in `catalog/contract/contract.lovable.json`. `verify_contract.py` diffs the two
and fails on:

- a missing top-level key (`household`, `panels`, `inverters`, `batteries`,
  `suppliers`, `listings`, `configurations`, `installedSystem`)
- a field under the wrong name
- a configuration pointing at a part that is not in the catalogue
- `installedSystem.configuration_id` matching no configuration

Two traps worth knowing, both of which crash or silently mislead the app:

| | |
|---|---|
| `configurations` must exist and be non-empty | The build page runs `configurations.find(c => c.configuration_id === 'C2') ?? configurations[0]` with **no guard**. `undefined.find()` throws. The monitoring page resolves `installedSystem → configurations → panels/inverters/batteries`, so those ids must line up. `C1`/`C2`/`C3` are fixed names — `C2` is the app's default preset. |
| the field is `bms_family`, not `battery_comm_family` | The check is `battery.bms_family === inverter.bms_family`. With the wrong name both sides are `undefined`, and `undefined === undefined` is `true` — so it **passes for the wrong reason** instead of failing. An earlier version of this builder had exactly that bug. |

## What is here and what is not

| | |
|---|---|
| Panels | **complete** — 3,368 rows, full electrical data |
| Inverters | **complete for now** — 4 Deye SG04LP1-EU models, 230 V |
| Batteries | **one** — Deye RW-F10.2, 43.2–57.6 V, inside the inverter's 40–60 V window |
| Prices and shops | **absent** — see below |

**Inverters are Deye only.** CEC is California; it has no entry for Deye, which
is one of the most common hybrid brands in the Philippines. So the panels come
from CEC and the inverters and battery come from manufacturer pages, each row
carrying its `source` URL.

**Prices need a Philippine shop.** Fill in `catalog/listings.seed.json` — run
`build.py --seed` to generate it with real part ids and blank prices. Rows left
blank are dropped by `build.py` and never reach the app, so a half-filled file is
safe. Until there are prices, the app's Budget and Stock checks read *"Needs
Changing"* and that is honest: guessing a price makes the budget check lie.

## Two things to check before trusting this

1. `PH_MAKES` in `build.py` is a **guess** at which makes are sold in the
   Philippines. It decides 17,000 of CEC's 21,700 rows. Verify it against a
   supplier.
2. `HOUSEHOLD` in `build.py` is the demo's placeholder (450 kWh/month,
   ₱250,000). It is what the Household step starts from, not a Philippine
   average. It is marked `is_synthetic: true`.

## Publishing

The app reads the file straight from the public repo, so publishing is a push:

```bash
python3 catalog/build.py --offline && python3 catalog/verify_contract.py \
  && git commit -am "catalog: rebuild" && git push
```

GitHub's raw CDN caches for about five minutes. The app appends a cache-busting
query string, so this does not matter in practice.

See `docs/LOVABLE_HANDOFF.md` for the one-line change on the app side.
