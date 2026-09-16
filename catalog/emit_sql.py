#!/usr/bin/env python3
"""Turn web/catalog.json into a Supabase migration the Lovable app can read.

The app does NOT hardcode demo data. src/lib/solar/catalog.functions.ts reads
eight Supabase tables with the publishable key:

    households, panels, inverters, batteries, suppliers, listings,
    configurations, installed_systems

So there is nothing to change in the frontend. We write real rows into those
tables and the site picks them up. This script generates the SQL.

    python3 catalog/build.py --offline
    python3 catalog/emit_sql.py                      # all 3,368 panels
    python3 catalog/emit_sql.py --panel-limit 40     # a usable dropdown
    python3 catalog/emit_sql.py --out supabase/migrations/20260916120000_real_parts.sql

The column list comes from the project's own migration
(20260910143947_*.sql), not from guesswork. Where our build carries a field
the table has no column for ("short_name", "manufacturer", "source"), it is
dropped: those live in web/catalog.json only.

SAFE TO RE-RUN. Every insert is an upsert. The demo rows are removed only
after the configurations have been repointed away from them, because
configurations.panel_id has a foreign key to panels.panel_id.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT.parent / "web" / "catalog.json"
# Repo root, so there is one obvious file to copy into the SQL Editor.
OUT = ROOT.parent / "REAL_PARTS.sql"

# Column lists, copied from supabase/migrations/20260910143947_*.sql.
COLUMNS = {
    "households": ["household_id", "name", "location", "timezone",
                   "monthly_consumption_kwh", "budget_php", "system_type",
                   "critical_load_kw", "target_backup_hours", "tariff_php_per_kwh",
                   "peak_sun_hours", "performance_ratio", "is_synthetic"],
    "panels": ["panel_id", "name", "rated_power_w", "vmp_v", "imp_a", "voc_v",
               "isc_a", "warranty_years"],
    "inverters": ["inverter_id", "name", "system_type", "rated_ac_power_kw",
                  "max_pv_power_kw", "mppt_min_v", "mppt_max_v", "max_dc_voltage_v",
                  "max_mppt_current_a", "max_mppt_isc_a", "mppt_count",
                  "battery_min_v", "battery_max_v", "max_battery_power_kw",
                  "bms_family", "monitoring_support"],
    "batteries": ["battery_id", "name", "nominal_capacity_kwh", "nominal_voltage_v",
                  "min_operating_voltage_v", "max_operating_voltage_v",
                  "max_charge_discharge_kw", "max_parallel_units", "bms_family"],
    "suppliers": ["supplier_id", "name", "location", "is_synthetic"],
    "listings": ["listing_id", "component_id", "component_type", "supplier_id",
                 "unit_price_php", "stock_units", "price_as_of", "is_synthetic"],
    "configurations": ["configuration_id", "household_id", "name", "panel_id",
                       "panel_count", "inverter_id", "battery_id", "battery_count",
                       "series_panels_per_string", "parallel_strings_per_mppt",
                       "used_mppt_count", "other_cost_allowance_php", "status"],
    "installed_systems": ["system_id", "household_id", "configuration_id",
                          "panel_capacity_kw", "inverter_capacity_kw",
                          "battery_capacity_kwh", "battery_min_soc_pct",
                          "battery_max_soc_pct", "initial_soc_pct",
                          "solar_dc_to_bus_efficiency", "battery_charge_efficiency",
                          "battery_discharge_efficiency", "source"],
}

PK = {"households": "household_id", "panels": "panel_id",
      "inverters": "inverter_id", "batteries": "battery_id",
      "suppliers": "supplier_id", "listings": "listing_id",
      "configurations": "configuration_id", "installed_systems": "system_id"}

# Columns that are NOT NULL in the schema but that we have no honest value for.
# The migration relaxes them; the app never reads warranty_years (checked against
# the deployed bundle), and inventing a number for 3,368 panels would be worse
# than a blank.
ALLOW_NULL = {"panels": {"warranty_years"}}

DEMO_PARTS = {
    "panels": ("P550", "P450"),
    "inverters": ("I5000", "I3000"),
    "batteries": ("B512", "BHV"),
    "suppliers": ("S1", "S2"),
}


def lit(value) -> str:
    """A PostgreSQL literal. Panels have names with commas and slashes in them."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def block(table: str, rows: list[dict], header: str = "") -> str:
    """One upsert statement per table — cheaper for the dashboard than per row."""
    if not rows:
        return f"-- {table}: nothing to write\n\n"
    cols = COLUMNS[table]
    values = []
    for row in rows:
        allowed = ALLOW_NULL.get(table, set())
        missing = [c for c in cols
                   if (c not in row or row[c] is None) and c not in allowed]
        if missing:
            raise SystemExit(f"{table}: row {row.get(PK[table])!r} is missing {missing}. "
                             f"Every column here is NOT NULL.")
        values.append("(" + ",".join(lit(row[c]) for c in cols) + ")")
    pk = PK[table]
    updatable = [c for c in cols if c != pk]
    sets = ", ".join(f"{c} = excluded.{c}" for c in updatable)
    out = [f"-- {header}" if header else f"-- {table}"]
    out.append(f"INSERT INTO public.{table} ({','.join(cols)}) VALUES")
    out.append(",\n".join(values))
    out.append(f"ON CONFLICT ({pk}) DO UPDATE SET {sets};")
    return "\n".join(out) + "\n\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--panel-limit", type=int, default=0,
                        help="keep only the N largest panels. The build page renders "
                             "every panel as a dropdown item, so 3,368 is unusable "
                             "without also changing the UI. 0 = keep all.")
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    panels = catalog["panels"]
    if args.panel_limit:
        # Always keep the panels the configurations reference, or the presets
        # point at rows that are not there and the foreign key blocks the insert.
        needed = {c["panel_id"] for c in catalog["configurations"]}
        keep = panels[:args.panel_limit]
        have = {p["panel_id"] for p in keep}
        keep += [p for p in panels if p["panel_id"] in needed and p["panel_id"] not in have]
        panels = keep

    # The demo rows use the same primary keys as ours for the household, the
    # configurations and the installed system. Upserting overwrites them.
    parts = {
        "households": [catalog["household"]],
        "panels": panels,
        "inverters": catalog["inverters"],
        "batteries": catalog["batteries"],
        "suppliers": catalog["suppliers"],
        "listings": catalog["listings"],
        "configurations": catalog["configurations"],
        "installed_systems": [catalog["installedSystem"]],
    }

    used_panels = {c["panel_id"] for c in catalog["configurations"]}
    kept = {p["panel_id"] for p in panels}
    if not used_panels <= kept:
        raise SystemExit(f"configurations point at {sorted(used_panels - kept)}, "
                         f"which are not in the panel set.")

    sql = [
        "-- Real parts for Solar Builder.",
        "-- Generated by catalog/emit_sql.py from web/catalog.json. Do not hand-edit.",
        "--",
        "-- The app reads these eight tables through its catalog server function,",
        "-- so nothing in src/ has to change. Safe to re-run.",
        "",
        "BEGIN;",
        "",
        "-- Visitor drafts reference the demo part ids. They are fictional, and the",
        "-- rows below replace them, so the drafts go first rather than block the",
        "-- delete with a foreign key error. Checklist rows follow via ON DELETE",
        "-- CASCADE from saved_builds.",
        "DELETE FROM public.checklist_items;",
        "DELETE FROM public.saved_builds;",
        "",
        "-- CEC publishes no warranty figure for solar modules. The column is",
        "-- NOT NULL and our source has no value, so relax it rather than invent",
        "-- one. The app does not read this field.",
        "ALTER TABLE public.panels ALTER COLUMN warranty_years DROP NOT NULL;",
        "",
        block("households", parts["households"], "The household the demo starts from"),
        block("panels", parts["panels"], f"{len(panels):,} panels"),
        block("inverters", parts["inverters"], "Hybrid inverters, 230 V"),
        block("batteries", parts["batteries"], "Battery"),
    ]

    if parts["suppliers"]:
        sql.append(block("suppliers", parts["suppliers"], "Shops"))
        sql.append(block("listings", parts["listings"],
                         "Prices. Only rows with a real quote."))
    else:
        sql += [
            "-- suppliers and listings are left empty on purpose: we have no",
            "-- Philippine quote yet, and a guessed price makes the budget check",
            "-- lie. The app reports 'Needs changing' for Budget and Stock, which",
            "-- is accurate. Add rows here when a real quote exists.",
            "DELETE FROM public.listings;",
            "DELETE FROM public.suppliers;",
            "",
        ]

    # Configurations must be repointed at the new parts BEFORE the demo parts go,
    # or the foreign key blocks the delete.
    sql.append(block("configurations", parts["configurations"],
                     "Presets. C2 is the build page's default."))
    sql.append(block("installed_systems", parts["installed_systems"],
                     "What the monitoring page simulates from."))

    sql.append("-- Now nothing refers to the fictional demo parts.")
    for table, ids in DEMO_PARTS.items():
        quoted = ",".join(lit(i) for i in ids)
        sql.append(f"DELETE FROM public.{table} WHERE {PK[table]} IN ({quoted});")
    sql.append("")
    sql.append("COMMIT;")
    sql.append("")
    sql.append("-- ---------------------------------------------------------------------")
    sql.append("-- Ran it? Then the SQL Editor shows this table straight away.")
    sql.append(f"-- Expect: panels {len(panels)}, inverters {len(parts['inverters'])}, "
               f"batteries {len(parts['batteries'])}, configurations {len(parts['configurations'])},")
    sql.append("-- suppliers 0, listings 0. Suppliers and listings are empty on purpose.")
    sql.append("-- ---------------------------------------------------------------------")
    sql.append("SELECT 'batteries' AS table_name, count(*) AS rows FROM public.batteries")
    sql.append("UNION ALL SELECT 'configurations', count(*) FROM public.configurations")
    sql.append("UNION ALL SELECT 'inverters', count(*) FROM public.inverters")
    sql.append("UNION ALL SELECT 'listings', count(*) FROM public.listings")
    sql.append("UNION ALL SELECT 'panels', count(*) FROM public.panels")
    sql.append("UNION ALL SELECT 'suppliers', count(*) FROM public.suppliers")
    sql.append("ORDER BY table_name;")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(sql), encoding="utf-8")

    size = args.out.stat().st_size
    print(f"wrote {args.out}  ({size // 1024:,} KB)")
    print(f"  panels           {len(panels):>7,}"
          + (f"   (of {len(catalog['panels']):,} — dropdown limit)" if args.panel_limit else ""))
    print(f"  inverters        {len(parts['inverters']):>7,}")
    print(f"  batteries        {len(parts['batteries']):>7,}")
    print(f"  configurations   {len(parts['configurations']):>7,}")
    print(f"  suppliers        {len(parts['suppliers']):>7,}")
    print(f"  listings         {len(parts['listings']):>7,}")
    print()
    print("Apply it: Supabase dashboard -> SQL Editor -> paste -> Run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
