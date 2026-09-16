# Handoff: wiring the real parts catalogue into the Lovable app

**For:** whoever has access to the Lovable project
(`lovp_3nnha08p439h5svyvjfgqtq615`, deployed at `sun-plan-build.lovable.app`).

**From:** the data/backend side. We own `catalog/build.py`, not `src/`.

**What we need from you:** one change, in one function. Nothing else.

---

## Why

The deployed `catalog` server function returns **hand-written demo data** —
"Demo Sun 450", "Demo Solar Shop A". The backend now produces a real
catalogue: 3,368 panels from NREL's CEC list, Deye hybrid inverters and a
Deye battery with datasheet specs.

The payload shape is already identical. We captured what your function returns
today and kept it as `catalog/contract/contract.lovable.json`; our output is
diffed against it field for field on every build. So this is a swap of the
**source**, not a rewrite of the shape.

Live URL (public repo, no key needed):

```
https://raw.githubusercontent.com/DataHub2/Innovation_Pioneers_SD7_MLops_team/main/web/catalog.json
```

---

## The change

Find the server function behind `queryKey: ['catalog']`. It currently builds an
object literal with `household`, `panels`, `inverters`, … and returns it.

**Swap its body for this.** It falls back to your demo data on *any* problem —
a failed fetch, a 404, or a 200 carrying the wrong shape — so the site cannot be
broken by our side being late, down, or wrong:

```ts
const CATALOG_URL =
  'https://raw.githubusercontent.com/DataHub2/Innovation_Pioneers_SD7_MLops_team/main/web/catalog.json'

// The payload must have these or the app throws on `.find()` / `.household`.
// Checked rather than trusted: a 200 with the wrong shape is the failure mode
// that a try/catch alone does not catch.
function isUsable(d: unknown): boolean {
  const c = d as Record<string, any> | null
  return !!c
    && !!c.household
    && Array.isArray(c.panels) && c.panels.length > 0
    && Array.isArray(c.inverters) && c.inverters.length > 0
    && Array.isArray(c.batteries) && c.batteries.length > 0
    && Array.isArray(c.configurations) && c.configurations.length > 0
    && !!c.installedSystem
}

export const fetchCatalog = createServerFn({ method: 'GET' }).handler(async () => {
  try {
    // ?v= busts GitHub's ~5 minute CDN cache so refreshes are immediate.
    const res = await fetch(`${CATALOG_URL}?v=${Date.now()}`, { cache: 'no-store' })
    if (!res.ok) throw new Error(`catalog HTTP ${res.status}`)
    const data = await res.json()
    if (!isUsable(data)) throw new Error('catalog shape not usable')
    return data
  } catch (error) {
    console.error('[catalog] live fetch failed, using demo data:', error)
    return DEMO_CATALOG   // <- the object literal you are replacing; keep it
  }
})
```

Keep the query key `['catalog']` and its `staleTime`. Do not rename anything.

**This makes the order of operations irrelevant.** You can ship this before our
file is published: it will log a warning and serve your demo data exactly as it
does today, then pick up the real catalogue on the next request once our side
is live. If you would rather not have the validation, say so and we will
sequence the push first instead.

---

## Verify

1. Open `/build`. The parts dropdowns should list real models
   (e.g. *JA Solar JAM72D30-550/MB*, *Deye SUN-5K-SG04LP1-EU*), not "Demo Sun 450".
2. The system preset should read **Balanced (C2)** by default — 10 panels,
   Deye SUN-5K, 1 battery.
3. Open `/monitoring`. It resolves `installedSystem.configuration_id → C2` and
   shows the matching panel/inverter/battery names.
4. Open `/compare`. Three presets: C1 Budget, C2 Balanced, C3 Backup.

If step 1 still shows demo names, the deploy has not picked up the change.

---

## Please do not "fix" these

Two things in the payload look like mistakes and are deliberate:

- **`bms_family`** on both the battery and the inverter. Your check is
  `battery.bms_family === inverter.bms_family`. An earlier version of our
  builder emitted `battery_comm_family`, which made both sides `undefined` —
  and `undefined === undefined` is `true`, so the check **passed for the wrong
  reason**. The contract test now fails the build if that field reappears.
- **Extra keys** `built_utc`, `source`, `counts`. The app ignores them; they
  make a stale file obvious during debugging, and our own `web/index.html`
  reads the first two.

---

## Known gaps on our side (not yours to solve)

- **Prices and stock are empty.** `listings` has no rows yet, so the Budget and
  Stock checks will read *"Needs changing"* and totals show as unavailable.
  That is accurate — we have no Philippine quotes yet. It is not a bug in your
  code, and it will fill in without a frontend change once we have them.
- **The monitoring telemetry is still synthetic.** The 2,016 readings were
  simulated for the old demo system (4.4 kW array). Our C2 preset is 5.5 kW
  (10 × 550 W), so the monitoring page will label the system 5.5 kW while the
  charts show the old array's output. Visible, mildly inconsistent, harmless.
- **The footer says everything is fictional.** Panels and inverters are now
  real published specs. If you want, and only if you want, that sentence in the
  layout should be softened to say prices and monitoring readings are the
  synthetic part.

---

## If you would rather not touch it

That is fine — tell us and we will go the other way: push the JSON into a
Supabase Storage bucket your server function reads. It still needs a change to
that same function, so the effort is roughly equal. The GitHub route just needs
no secret.
