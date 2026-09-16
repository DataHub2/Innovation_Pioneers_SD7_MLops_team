#!/usr/bin/env python3
"""Check web/catalog.json against the contract captured from the live app.

Compares against catalog/contract/contract.lovable.json — the real payload the
deployed `catalog` server function returns. Catches the failure mode we already
hit once: a file that looks fine but has a field under the wrong name, so a
check passes for the wrong reason instead of failing.

    python3 catalog/verify_contract.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILT = ROOT.parent / "web" / "catalog.json"
CONTRACT = ROOT / "contract" / "contract.lovable.json"

problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def note(msg: str) -> None:
    notes.append(msg)


# plural collection -> the id field on its rows
ID_FIELD = {"panels": "panel_id", "inverters": "inverter_id",
            "batteries": "battery_id", "suppliers": "supplier_id",
            "configurations": "configuration_id", "listings": "listing_id"}

# In the contract but not read anywhere in the deployed bundle (verified against
# all 31 chunks). A null here is honest, not a defect.
UNREAD = {"warranty_years", "short_name", "manufacturer", "source", "chemistry",
          "usable_capacity_kwh", "ac_voltage_v", "max_parallel_units"}


def type_of(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    return "object"


def want_fields(where: str, item: dict, template: dict, required: bool) -> None:
    """Field names must line up. Missing optional fields are a note, not a failure."""
    for key, value in template.items():
        if key not in item:
            (fail if required else note)(
                f"{where}: missing '{key}' (contract has it as {type_of(value)})")
        elif item[key] is None and key in UNREAD:
            note(f"{where}.{key}: null, and the app never reads it")
        elif type_of(item[key]) != type_of(value) and value is not None:
            fail(f"{where}.{key}: got {type_of(item[key])}, contract has {type_of(value)}")


def main() -> int:
    if not BUILT.exists():
        print(f"missing {BUILT}. Run: python3 catalog/build.py --offline")
        return 2
    if not CONTRACT.exists():
        print(f"missing {CONTRACT}")
        return 2

    built = json.loads(BUILT.read_text(encoding="utf-8"))
    live = json.loads(CONTRACT.read_text(encoding="utf-8"))

    # 0. primary keys must be unique. Postgres rejects a whole migration with
    # "ON CONFLICT DO UPDATE cannot affect row a second time" if not, and the
    # message does not say which table.
    for key, field in ID_FIELD.items():
        rows = built.get(key)
        if not isinstance(rows, list):
            continue
        dupes = [k for k, n in Counter(r.get(field) for r in rows).items() if n > 1]
        if dupes:
            fail(f"{key}.{field}: {len(dupes)} duplicate id(s), e.g. {dupes[:3]}. "
                 f"The migration would fail on ON CONFLICT.")

    # 1. every key the app reads must be here, with the same type
    for key, value in live.items():
        if key not in built:
            fail(f"top level: missing '{key}' ({type_of(value)}) — the app reads this")
        elif type_of(built[key]) != type_of(value):
            fail(f"top level: '{key}' is {type_of(built[key])}, contract has {type_of(value)}")

    # 2. object shapes
    for key in ("household", "installedSystem"):
        if isinstance(built.get(key), dict) and isinstance(live.get(key), dict):
            want_fields(key, built[key], live[key], required=False)

    # 3. arrays must be non-empty and their rows must share the contract's field names
    for key in ("panels", "inverters", "batteries", "configurations"):
        rows = built.get(key)
        if not isinstance(rows, list) or not rows:
            fail(f"{key}: must be a non-empty array "
                 f"(the app calls .find() on it with no guard)")
            continue
        template = live.get(key)
        if isinstance(template, list) and template:
            want_fields(f"{key}[0]", rows[0], template[0], required=True)

    # 4. the trap: bms_family, not battery_comm_family
    for key in ("inverters", "batteries"):
        for row in built.get(key) or []:
            if "battery_comm_family" in row:
                fail(f"{key}/{row.get(ID_FIELD[key])}: still has "
                     f"'battery_comm_family' — the app reads 'bms_family', so the "
                     f"check compares undefined to undefined and passes wrongly")
            if "bms_family" not in row:
                fail(f"{key}/{row.get(ID_FIELD[key])}: no 'bms_family'")

    inv_families = {r.get("bms_family") for r in built.get("inverters") or []}
    bat_families = {r.get("bms_family") for r in built.get("batteries") or []}
    if inv_families and bat_families and not (inv_families & bat_families):
        fail(f"no battery shares an inverter's bms_family "
             f"(inverters {inv_families}, batteries {bat_families})")

    # 5. the app asks for C2 by name, and monitoring resolves installedSystem -> configuration
    configs = built.get("configurations") or []
    ids = {c.get("configuration_id") for c in configs}
    if "C2" not in ids:
        note("no configuration named 'C2' — the build page looks for it first "
             "and falls back to configurations[0]")
    installed = built.get("installedSystem") or {}
    if installed.get("configuration_id") not in ids:
        fail(f"installedSystem.configuration_id="
             f"{installed.get('configuration_id')!r} matches no configuration; "
             f"the monitoring page will show no system detail")

    # 6. every configuration must point at parts that exist
    have = {k: {r.get(ID_FIELD[k]) for r in built.get(k) or []}
            for k in ("panels", "inverters", "batteries")}
    for config in configs:
        for kind, field in (("panels", "panel_id"), ("inverters", "inverter_id"),
                            ("batteries", "battery_id")):
            if config.get(field) not in have[kind]:
                fail(f"configuration {config.get('configuration_id')}: "
                     f"{field}={config.get(field)!r} is not in {kind}")

    # 7. listings must be usable, or honestly absent
    listings = built.get("listings") or []
    known = {s.get("supplier_id") for s in built.get("suppliers") or []}
    for row in listings:
        if row.get("supplier_id") not in known:
            fail(f"listing {row.get('listing_id')}: unknown supplier_id")
        if not isinstance(row.get("unit_price_php"), (int, float)):
            fail(f"listing {row.get('listing_id')}: unit_price_php is not a number")
        if not isinstance(row.get("stock_units"), int):
            fail(f"listing {row.get('listing_id')}: stock_units is not an integer")
    if not listings:
        note("no listings, so the Budget and Stock checks will read 'Needs changing'")

    print(f"built:    {BUILT}")
    print(f"contract: {CONTRACT}")
    print()
    for msg in notes:
        print(f"  note   {msg}")
    for msg in problems:
        print(f"  FAIL   {msg}")
    print()
    if problems:
        print(f"{len(problems)} problem(s). The app would misbehave.")
        return 1
    print("OK — shape matches the deployed contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
