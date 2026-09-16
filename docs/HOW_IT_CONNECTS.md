# How the backend reaches the site

Written after reading the Lovable project's source. An earlier version of this
pair of files told the frontend owner to change a server function to fetch
`web/catalog.json` from GitHub. **That was wrong and the files are deleted.**
Nothing in `src/` needs to change.

## The actual path

`src/lib/solar/catalog.functions.ts` in the Lovable project is a TanStack Start
server function that reads **eight Supabase tables** with the publishable key:

```
households  panels  inverters  batteries  suppliers  listings
configurations  installed_systems
```

It does not hardcode anything. So the integration is not a code change at all —
it is data. We write real rows into those tables and the site picks them up.

```
catalog/build.py      CEC + datasheets  ->  web/catalog.json
catalog/emit_sql.py   web/catalog.json  ->  REAL_PARTS.sql
                      REAL_PARTS.sql    ->  Supabase SQL Editor  ->  live site
```

`web/catalog.json` is still useful on its own: it feeds `web/index.html` and it
is the thing `verify_contract.py` checks. But it is an intermediate file, not
the integration point.

## Why the column names are not ours to choose

`catalog/emit_sql.py` takes its column lists from the project's own migration,
`supabase/migrations/20260910143947_*.sql`. Three things that follow from it and
that are easy to get wrong:

| | |
|---|---|
| `panels.warranty_years` is `NOT NULL` | CEC publishes no warranty figure. The migration relaxes the column rather than inventing a number for 3,365 panels. The app never reads it. |
| `configurations.panel_id` is a foreign key | Configurations must be repointed at the new parts **before** the demo parts are deleted, or the delete is blocked. `emit_sql.py` orders it that way. |
| every primary key must be unique | `panel_id` used to be the name slug cut to 40 characters. The slug starts with the manufacturer, so the cut landed before the model number and 94 ids collided. Postgres rejects the whole migration with *"ON CONFLICT DO UPDATE cannot affect row a second time"* and does not name the table. `verify_contract.py` now fails on any duplicate key. |

## The panel count is a UI constraint, not a data one

`src/routes/build.tsx` renders *every* panel as a `<SelectItem>`. CEC has 3,365
after filtering; a dropdown with 3,365 entries is unusable, so `emit_sql.py`
writes the largest 60 plus whichever panels the presets reference. Lifting this
needs a searchable combobox in the build route, not more data.

## What is still missing

`suppliers` and `listings` are empty. The app's Budget and Stock checks read
"Needs changing" and step 4 (My Checklist) produces no shopping list. That is
accurate — there is no Philippine quote yet. Filling in
`catalog/listings.seed.json` is the way to fix it, and it needs no frontend
change.

The monitoring telemetry (2,016 readings for SYS001) is still the synthetic
series generated for the old 4.4 kW demo system, while C2 is now 5.5 kW. The
page labels the system 5.5 kW and plots the old array's output.
