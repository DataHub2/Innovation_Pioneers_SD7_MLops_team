#!/usr/bin/env python3
"""Build the parts list for Solar Builder — in the exact shape the app reads.

Writes web/catalog.json with the eight keys the Lovable page's `catalog`
server function returns today. Captured from the live deployment and kept as
a fixture in catalog/contract/contract.lovable.json, so the shape can be
diffed instead of guessed:

    household  panels  inverters  batteries  suppliers  listings
    configurations  installedSystem

Two rules that are not obvious, and both crash the app if broken:

  * `configurations` must exist and be a non-empty array. The build page runs
    `configurations.find(c => c.configuration_id === 'C2') ?? configurations[0]`
    with no guard, and the monitoring page looks up the configuration that
    `installedSystem.configuration_id` points at. So C1/C2/C3 are fixed names
    and they must reference ids that are actually present in panels/inverters/
    batteries below.
  * The comm-family field is `bms_family` on BOTH the battery and the inverter.
    The app compares `battery.bms_family === inverter.bms_family`. Shipping
    `battery_comm_family` like this file used to makes both sides `undefined`,
    and `undefined === undefined` is true — the check passes for the wrong
    reason instead of failing loudly.

Panels come from CEC (open data, published by NREL). Inverters, batteries and
shops come from the curated block below, because CEC is California and has
neither the cheap Chinese hybrids sold in the Philippines nor any batteries.

    python3 catalog/build.py            # first run downloads the CEC list
    python3 catalog/build.py --offline  # use the cached copy
    python3 catalog/build.py --seed     # also write catalog/listings.seed.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
OUT = ROOT.parent / "web" / "catalog.json"
SEED = ROOT / "listings.seed.json"

CEC_MODULES = ("https://raw.githubusercontent.com/NREL/SAM/develop/deploy/"
               "libraries/CEC%20Modules.csv")

# Makes sold in the Philippines. [UNVERIFIED] This decides 17,000 of CEC's 21,700
# rows, so if it is wrong the panel list is wrong. Check against a local supplier.
PH_MAKES = ("jinko", "trina", "longi", "ja solar", "risen", "dmegc", "talesun",
            "canadian", "sunpower", "rec ", "q cells", "hanwha", "hyundai")

BRAND_CASE = {"solaredge": "SolarEdge", "goodwe": "GoodWe", "solax": "SolaX",
              "longi": "LONGi", "ja solar": "JA Solar", "dmegc": "DMEGC",
              "qcells": "Qcells", "sma": "SMA", "abb": "ABB", "canadian": "Canadian Solar"}
BRANDS = sorted(("solaredge", "power electronics", "united renewable", "growatt",
                 "deye", "sungrow", "goodwe", "solis", "solax", "huawei", "victron",
                 "fronius", "jinko", "trina", "longi", "ja solar", "risen", "dmegc",
                 "talesun", "canadian", "sunpower", "qcells", "hanwha", "hyundai"),
                key=len, reverse=True)

# ---------------------------------------------------------------------------
# CURATED PARTS — the Philippines
#
# Specs below are read off the manufacturer's own product page. Every model
# carries the URL it came from. Nothing here is from memory.
#
# Still MISSING, and deliberately left empty rather than guessed:
#   * prices   — need a Philippine shop. Guess a price and the budget check lies.
#   * stock    — no shop exposes it reliably; see the note in README.md.
#   Fill in catalog/listings.seed.json (build.py --seed writes it) when you have
#   real quotes. Until then `listings` stays empty and the app says so.
# ---------------------------------------------------------------------------

DEYE_SG04 = "https://www.deyeinverter.com/product/single-phase-low-voltage-hybrid-inverter/sun3-3-6-5-6ksg04lp1-3-6kw-single-phase.html"

# The comm-family string must match on both sides or the app's `bms` check fails.
# Deye calls it "self-adaption to BMS"; CAN2.0/RS485 on the battery side.
DEYE_LV_BMS = "Deye LV BMS"

# model,          rated kW, max PV kW, Voc max, I max, Isc max, MPPT low/high, MPPT count
INVERTERS = [
    ("SUN-3K-SG04LP1-EU", 3.0, 6.0, 500, 18, 27, 150, 425, 1),
    ("SUN-3.6K-SG04LP1-EU", 3.6, 7.2, 500, 18, 27, 150, 425, 1),
    ("SUN-5K-SG04LP1-EU", 5.0, 10.0, 500, 18, 27, 150, 425, 2),
    ("SUN-6K-SG04LP1-EU", 6.0, 12.0, 500, 18, 27, 150, 425, 2),
]

RW_F10_2 = "https://deyeess.com/product/rw-f10-2/"


def inverter_records() -> list[dict]:
    out = []
    for name, ac, pv, vmax, imax, iscmax, low, high, mppt in INVERTERS:
        out.append({
            "inverter_id": "deye-" + re.sub(r"[^a-z0-9]+", "-", name.lower()),
            "name": f"Deye {name}",
            "short_name": f"Deye {name.split('-', 1)[1]}",
            "manufacturer": "Deye",
            "system_type": "hybrid",
            "rated_ac_power_kw": ac,
            "max_pv_power_kw": pv,
            "max_dc_voltage_v": float(vmax),
            "max_mppt_current_a": float(imax),
            "max_mppt_isc_a": float(iscmax),
            "mppt_min_v": float(low),
            "mppt_max_v": float(high),
            "mppt_count": mppt,
            "battery_min_v": 40.0,
            "battery_max_v": 60.0,
            "max_battery_power_kw": round(ac, 1),
            # NOT battery_comm_family. See the note in the module docstring.
            "bms_family": DEYE_LV_BMS,
            "max_parallel_units": 16,
            "ac_voltage_v": 230,
            "monitoring_support": "none",
            "source": DEYE_SG04,
        })
    return out


# Deye RW-F10.2 — LiFePO4, low-voltage, the battery Deye pairs with SG04LP1.
# 43.2-57.6 V sits inside the inverter's 40-60 V window, so the app's
# battery-voltage check passes on real datasheets, not on an assumption.
BATTERIES: list[dict] = [{
    "battery_id": "deye-rw-f10-2",
    "name": "Deye RW-F10.2",
    "short_name": "Deye RW-F10.2",
    "manufacturer": "Deye",
    "nominal_capacity_kwh": 10.2,
    "usable_capacity_kwh": 9.2,
    "nominal_voltage_v": 51.2,
    "min_operating_voltage_v": 43.2,
    "max_operating_voltage_v": 57.6,
    "max_charge_discharge_kw": 5.0,
    "max_parallel_units": 32,
    "bms_family": DEYE_LV_BMS,
    "chemistry": "LiFePO4",
    "source": RW_F10_2,
}]


# ---------------------------------------------------------------------------
# HOUSEHOLD — the default the Household step starts from.
#
# These are the demo's placeholder numbers, not a Philippine average. A visitor
# overwrites them in step 1. Marked synthetic until someone sources real ones.
# ---------------------------------------------------------------------------

HOUSEHOLD = {
    "household_id": "HH001",
    "name": "Demo Household",
    "location": "Laguna, Philippines",
    "timezone": "Asia/Manila",
    "monthly_consumption_kwh": 450,
    "budget_php": 250000,
    "system_type": "hybrid",
    "critical_load_kw": 0.5,
    "target_backup_hours": 8,
    "tariff_php_per_kwh": 12,
    "peak_sun_hours": 4.5,
    "performance_ratio": 0.8,
    "is_synthetic": True,
}

# The build page hardcodes a preference for `C2`. Do not renumber these.
#
# The match string must be the full "SUN-xK-" prefix. A bare "6K-" also matches
# "Deye SUN-3.6K-SG04LP1-EU", which silently gives C3 a 3.6 kW inverter with two
# parallel strings on its single MPPT — 2 x 13.9 A against a 27 A limit.
# configuration_id, label, panel_count, inverter match string, battery_count
CONFIG_PLANS = [
    ("C1", "Budget",   6,  "SUN-3K-",  1),
    ("C2", "Balanced", 10, "SUN-5K-",  1),
    ("C3", "Backup",   14, "SUN-6K-",  2),
]

# What monitoring is simulated from, before anyone wires up real hardware.
INSTALLED_SYSTEM_CONFIG = "C2"
INSTALLED_SYSTEM_EFFICIENCIES = {
    "battery_min_soc_pct": 20.0,
    "battery_max_soc_pct": 95.0,
    "initial_soc_pct": 65.0,
    "solar_dc_to_bus_efficiency": 0.96,
    "battery_charge_efficiency": 0.95,
    "battery_discharge_efficiency": 0.95,
    "source": "synthetic_simulator",
}


# ---------------------------------------------------------------------------

def rows(offline: bool):
    path = CACHE / "modules.csv"
    if not path.exists():
        if offline:
            raise SystemExit(f"{path} is missing. Run once without --offline.")
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(CEC_MODULES, headers={"User-Agent": "solar-builder/2"})
        try:
            payload = urllib.request.urlopen(request, timeout=120).read()
        except urllib.error.URLError as error:
            if "CERTIFICATE_VERIFY_FAILED" not in str(error):
                raise
            import certifi  # Python without system certificates, common on macOS
            context = ssl.create_default_context(cafile=certifi.where())
            payload = urllib.request.urlopen(request, timeout=120, context=context).read()
        path.write_bytes(payload)
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            if (row.get("Name") or "").strip():
                yield row


def num(row: dict, key: str) -> float | None:
    raw = (row.get(key) or "").strip()
    if not raw or raw.lower() in {"nan", "none", "n/a"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def brand_of(text: str) -> str:
    low = (text or "").lower()
    for brand in BRANDS:
        if brand in low:
            return BRAND_CASE.get(brand, brand.title())
    return ""


def short_name(name: str, manufacturer: str = "") -> str:
    model = name.split(":")[-1].strip() if ":" in name else name.strip()
    if manufacturer and model.lower().startswith(manufacturer.lower()):
        model = model[len(manufacturer):].strip()
    model = re.sub(r"\s*\{[^}]*\}\s*$", "", model).strip()
    brand = brand_of(name) or brand_of(manufacturer)
    return f"{brand} {model}".strip() if brand and brand.lower() not in model.lower() else (model or name)


def panel_id(name: str, used: set[str]) -> str:
    """A stable id that is actually unique.

    This used to be the slug truncated to 40 characters. The slug starts with
    the manufacturer, so the cut landed before the model number and every
    module from a maker with a long name collapsed onto one id — 94 collisions
    across CEC, which Postgres rejects with "ON CONFLICT DO UPDATE cannot
    affect row a second time".
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    candidate = "cec-" + (slug or "unnamed")
    if candidate in used:
        candidate = f"cec-{slug}-{hashlib.md5(name.encode()).hexdigest()[:6]}"
    suffix = 2
    unique = candidate
    while unique in used:
        unique = f"{candidate}-{suffix}"
        suffix += 1
    return unique


def panels(offline: bool):
    out, dropped = [], {"make": 0, "small": 0, "odd": 0, "dupe": 0}
    seen_names: set[str] = set()
    used_ids: set[str] = set()
    for row in rows(offline):
        maker = (row.get("Manufacturer") or "").strip()
        if not any(b in maker.lower() for b in PH_MAKES):
            dropped["make"] += 1
            continue
        power, voc, vmp = num(row, "STC"), num(row, "V_oc_ref"), num(row, "V_mp_ref")
        imp, isc = num(row, "I_mp_ref"), num(row, "I_sc_ref")
        if None in (power, voc, vmp, imp, isc):
            dropped["odd"] += 1
            continue
        if power < 300:
            dropped["small"] += 1
            continue
        if not (0 < vmp < voc and 0 < imp <= isc):
            dropped["odd"] += 1
            continue
        name = row["Name"].strip()
        if name in seen_names:
            # CEC lists the same module more than once. Same module, one row.
            dropped["dupe"] += 1
            continue
        seen_names.add(name)
        pid = panel_id(name, used_ids)
        used_ids.add(pid)
        out.append({
            "panel_id": pid,
            "name": name,
            "short_name": short_name(name, maker),
            "manufacturer": maker,
            "rated_power_w": round(power, 1),
            "voc_v": round(voc, 3),
            "vmp_v": round(vmp, 3),
            "imp_a": round(imp, 3),
            "isc_a": round(isc, 3),
            # CEC does not publish a warranty figure. Left null on purpose —
            # the app does not read it (checked against the deployed bundle).
            "warranty_years": None,
            "source": "CEC Modules (NREL SAM)",
        })
    out.sort(key=lambda p: (-p["rated_power_w"], p["short_name"].lower()))
    return out, dropped


def pick_panel(panel_list: list[dict], target_w: int) -> dict:
    """The panel closest to a wanted wattage, so a preset does not silently drift."""
    return min(panel_list, key=lambda p: abs(p["rated_power_w"] - target_w))


def pick_inverter(inverter_list: list[dict], needle: str) -> dict:
    for inv in inverter_list:
        if needle in inv["name"]:
            return inv
    return inverter_list[0]   # never None: configurations must reference a real part


def series_count(panel: dict, inverter: dict) -> int:
    """How many panels in series before you exceed the inverter's DC window.

    Largest n where n*Voc stays under the max DC voltage and n*Vmp still reaches
    the MPPT floor. Cold mornings raise Voc, so this is an upper bound, not a
    guarantee — a real installer checks the temperature coefficient.
    """
    n = 1
    while n < 30 and (n + 1) * panel["voc_v"] <= inverter["max_dc_voltage_v"]:
        n += 1
    while n > 1 and n * panel["vmp_v"] > inverter["mppt_max_v"]:
        n -= 1
    while n > 1 and n * panel["vmp_v"] < inverter["mppt_min_v"]:
        n -= 1
    return max(n, 1)


def build_configurations(panel_list, inverter_list) -> list[dict]:
    out = []
    for cid, label, count, needle, batteries in CONFIG_PLANS:
        panel = pick_panel(panel_list, 550)
        inverter = pick_inverter(inverter_list, needle)
        # You cannot wire more panels in series than the string actually has.
        per_string = min(series_count(panel, inverter), count)
        strings = -(-count // per_string)              # ceil
        out.append({
            "configuration_id": cid,
            "household_id": HOUSEHOLD["household_id"],
            "name": label,
            "panel_id": panel["panel_id"],
            "panel_count": count,
            "inverter_id": inverter["inverter_id"],
            "battery_id": BATTERIES[0]["battery_id"],
            "battery_count": batteries,
            "series_panels_per_string": per_string,
            "parallel_strings_per_mppt": -(-strings // max(inverter["mppt_count"], 1)),
            "used_mppt_count": min(inverter["mppt_count"], strings),
            "other_cost_allowance_php": 25000,
            "status": "demo_planning_only",
        })
    return out


def build_installed_system(configurations, panel_list, inverter_list) -> dict:
    config = next(c for c in configurations
                  if c["configuration_id"] == INSTALLED_SYSTEM_CONFIG)
    panel = next(p for p in panel_list if p["panel_id"] == config["panel_id"])
    inverter = next(i for i in inverter_list if i["inverter_id"] == config["inverter_id"])
    battery = next(b for b in BATTERIES if b["battery_id"] == config["battery_id"])
    return {
        "system_id": "SYS001",
        "household_id": HOUSEHOLD["household_id"],
        "configuration_id": config["configuration_id"],
        "panel_capacity_kw": round(config["panel_count"] * panel["rated_power_w"] / 1000, 2),
        "inverter_capacity_kw": inverter["rated_ac_power_kw"],
        "battery_capacity_kwh": round(config["battery_count"] * battery["nominal_capacity_kwh"], 2),
        **INSTALLED_SYSTEM_EFFICIENCIES,
    }


def load_listings() -> tuple[list[dict], list[dict], dict]:
    """Read catalog/listings.seed.json, keeping only rows that are actually filled in.

    A listing with no price or no stock is dropped rather than shipped as 0:
    the app treats 0 stock as "Sold out", which would be a lie about a shop we
    have not checked.
    """
    if not SEED.exists():
        return [], [], {"present": False}
    raw = json.loads(SEED.read_text(encoding="utf-8"))
    suppliers = [s for s in raw.get("suppliers", [])
                 if (s.get("name") or "").strip()]
    known = {s["supplier_id"] for s in suppliers}
    listings, dropped = [], 0
    for row in raw.get("listings", []):
        price, stock = row.get("unit_price_php"), row.get("stock_units")
        if not isinstance(price, (int, float)) or price <= 0:
            dropped += 1
            continue
        if not isinstance(stock, int) or stock <= 0:
            dropped += 1
            continue
        if row.get("supplier_id") not in known:
            dropped += 1
            continue
        listings.append({
            "listing_id": row["listing_id"],
            "component_type": row["component_type"],
            "component_id": row["component_id"],
            "supplier_id": row["supplier_id"],
            "unit_price_php": price,
            "stock_units": stock,
            "price_as_of": row.get("price_as_of") or date.today().isoformat(),
            "is_synthetic": bool(row.get("is_synthetic", True)),
        })
    return suppliers, listings, {"present": True, "dropped": dropped}


# Demo prices, derived from the levels the app's own demo used, scaled to our
# parts: PHP 11.82/W for panels, PHP 11,000/kW for inverters, PHP 45,000 for the
# battery. Every row is written with is_synthetic = true, and the app's footer
# and the shopping-list PDF both already say prices are fictional. Replace these
# with real quotes and nothing else has to change.
PANEL_PHP_PER_W = 12.0
INVERTER_PHP_PER_KW = 11000.0
BATTERY_PHP = 45000.0
SEED_STOCK = 9999
SEED_PANEL_LIMIT = 60          # must match emit_sql.py --panel-limit

DEMO_SHOP = {"supplier_id": "S1", "name": "Demo Solar Shop",
             "location": "Metro Manila", "is_synthetic": True}


def sample_price(kind: str, row: dict) -> float:
    if kind == "panel":
        return round(row["rated_power_w"] * PANEL_PHP_PER_W / 100) * 100
    if kind == "inverter":
        return round(row["rated_ac_power_kw"] * INVERTER_PHP_PER_KW / 100) * 100
    return BATTERY_PHP


def write_seed(panel_list, inverter_list) -> None:
    """Scaffold listings.seed.json with real ids and blank prices to fill in."""
    def row(lid: str, kind: str, cid: str, priced: dict) -> dict:
        return {"listing_id": lid, "component_type": kind, "component_id": cid,
                "supplier_id": "S1", "unit_price_php": sample_price(kind, priced),
                "stock_units": SEED_STOCK, "price_as_of": None,
                "is_synthetic": True}

    rows_out = [row(f"L-inv-{i:02d}", "inverter", inv["inverter_id"], inv)
                for i, inv in enumerate(inverter_list, start=1)]
    rows_out += [row(f"L-bat-{i:02d}", "battery", bat["battery_id"], bat)
                 for i, bat in enumerate(BATTERIES, start=1)]
    # Same panel set emit_sql.py writes, so nothing lands in the dropdown
    # without a price and a stock figure behind it.
    keep = panel_list[:SEED_PANEL_LIMIT]
    needed = {c["panel_id"] for c in build_configurations(panel_list, inverter_list)}
    have = {p["panel_id"] for p in keep}
    keep += [p for p in panel_list if p["panel_id"] in needed and p["panel_id"] not in have]
    for i, panel in enumerate(keep, start=1):
        rows_out.append(row(f"L-pnl-{i:02d}", "panel", panel["panel_id"], panel))
    payload = {
        "_readme": ("Demo prices, scaled from the levels the app's own demo used "
                    "(PHP 11.82/W panels, PHP 11,000/kW inverters). Every row is "
                    "is_synthetic: true, and the site's footer and the shopping-list "
                    "PDF both say prices are fictional. Replace unit_price_php with a "
                    "real quote and nothing else changes. A row with a null price or "
                    "null stock is dropped by build.py and never reaches the app."),
        "suppliers": [dict(DEMO_SHOP)],
        "listings": rows_out,
    }
    SEED.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--seed", action="store_true",
                        help="also write catalog/listings.seed.json to fill in")
    args = parser.parse_args()

    panel_list, dropped = panels(args.offline)
    inverter_list = inverter_records()

    if args.seed:
        write_seed(panel_list, inverter_list)

    configurations = build_configurations(panel_list, inverter_list)
    installed = build_installed_system(configurations, panel_list, inverter_list)
    suppliers, listings, listing_note = load_listings()

    catalog = {
        # The eight keys the app reads. Anything extra is ignored by JS.
        "household": HOUSEHOLD,
        "panels": panel_list,
        "inverters": inverter_list,
        "batteries": BATTERIES,
        "suppliers": suppliers,
        "listings": listings,
        "configurations": configurations,
        "installedSystem": installed,
        # Not part of the app's contract — but web/index.html reads `source`
        # and `built_utc` for its provenance line, so keep these names.
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Panels: CEC Modules (NREL). Inverters and battery: manufacturer pages.",
        "counts": {
            "panels": len(panel_list),
            "inverters": len(inverter_list),
            "batteries": len(BATTERIES),
            "suppliers": len(suppliers),
            "listings": len(listings),
            "configurations": len(configurations),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")

    print(f"wrote {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
    print(f"  panels          {len(panel_list):>6,}   "
          f"dropped {dropped['make']:,} other makes, {dropped['small']:,} small, "
          f"{dropped['odd']:,} unusable, {dropped['dupe']:,} duplicate names")
    print(f"  inverters       {len(inverter_list):>6,}   Deye SG04LP1-EU, 220/230 V")
    print(f"  batteries       {len(BATTERIES):>6,}   Deye RW-F10.2, 43.2-57.6 V")
    for config in configurations:
        print(f"  {config['configuration_id']:<2} {config['name']:<9} "
              f"{config['panel_count']:>3} panels  "
              f"{config['series_panels_per_string']} in series  "
              f"{config['battery_count']} battery")
    if not listing_note.get("present"):
        print("  suppliers           0   <-- no catalog/listings.seed.json yet")
        print(f"  listings            0   <-- run with --seed, then fill in prices")
    else:
        print(f"  suppliers   {len(suppliers):>6,}")
        print(f"  listings    {len(listings):>6,}   "
              f"({listing_note['dropped']} row(s) still blank, dropped)")
    if not listings:
        print()
        print("No priced listings, so the app's Budget and Stock checks will say")
        print("'Needs changing'. That is honest — nothing here is a quote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
