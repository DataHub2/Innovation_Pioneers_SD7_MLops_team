# Real parts for Solar Builder

The app's demo catalog is invented. This one is not — it is real solar panels and
inverters for a **Philippine home**, taken from open equipment lists published by
NREL. It is meant to be added to the Lovable site as a step, not to replace it.

Standard library only. No API key. No scraping of shops.

```
catalog/build.py     downloads the lists, filters them, writes web/catalog.json
web/index.html       the page. Two files, no build step
catalog/.cache/      the downloaded lists (gitignored)
```

## Run it

```bash
python3 catalog/build.py             # first run downloads the two lists
python3 -m http.server 8811 --directory web
# http://127.0.0.1:8811/
```

Every run prints what it kept and what it dropped:

```
panels      3,368   dropped 16,474 other makes, 1,837 small, 0 unusable
inverters   1,062   dropped 1,183 not home-sized, 100 unusable
              677 of them suit a 230 V Philippine home
```

## The page

Written for someone who has never seen a solar panel. No voltages, no jargon, no
numbers to look up. It asks two questions — which panel, which inverter — and
answers with the same words the app already uses: *"Looks OK in this demo"* or
*"Needs changing"*. The technical detail is hidden behind one "Show the numbers"
click, for an installer.

## What is here and what is not

| | |
|---|---|
| Panels | **complete** — full electrical data, including the temperature value the app is missing |
| Inverters | **nearly complete** — 1,062 home-sized, 677 of them right for a 230 V home |
| Batteries | **absent** |
| Prices and shops | **absent** |

**Batteries have no open source.** NREL publishes product lists for panels and
inverters because California regulates them for rebates. There is nothing like that
for batteries, so they have to come from manufacturer datasheets. Do not type
battery specs from memory into a tool that does electrical checks.

**One third of the inverters are the wrong mains voltage.** CEC is California. A
Philippine home is 230 V, so 240 V equipment is fine but 208 V (US three-phase) and
120 V (US split-phase) are not. The page checks this and says so in plain words.

**Two things to check before trusting this:**
1. The list of makes sold in the Philippines, in `build.py`, is a guess. It decides
   17,000 of the 21,700 modules. Verify it against a supplier.
2. Deye, Solis, Huawei, Victron and Canadian Solar have no entries in CEC at all.
   Deye is one of the most common hybrid brands in the Philippines.

## Adding it to the app

`web/catalog.json` uses the field names the app already reads, so the frontend does
not have to change. Either serve the file from the same server function the app's
`queryKey:['catalog']` uses, or write it into the database.

The app's checks must tolerate missing fields first — an inverter here has no
`mppt_count` or battery voltage, and reading those gives `null`. That change is in
her code, not this one.
