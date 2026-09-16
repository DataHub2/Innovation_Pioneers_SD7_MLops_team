#!/usr/bin/env python3
"""Build the parts list for Solar Builder.

Writes web/catalog.json in the exact shape the Lovable app reads, so her code can
swap its demo catalog for this one without a frontend change:

    {"suppliers": [...], "panels": [...], "inverters": [...],
     "batteries": [...], "listings": [...]}

Panels come from CEC (open data, published by NREL). Inverters, batteries and
shops come from the curated block below, because CEC is California and has
neither the cheap Chinese hybrids that are actually sold in the Philippines nor
any batteries at all.

    python3 catalog/build.py            # first run downloads the CEC list
    python3 catalog/build.py --offline  # use the cached copy
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
OUT = ROOT.parent / "web" / "catalog.json"

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
#   * batteries — need datasheets. Inventing a kWh figure is worse than a blank.
#   * stock    — no shop exposes it reliably; see the note in README.md.
# ---------------------------------------------------------------------------

# Deye SUN-3/3.6/5/6K-SG04LP1-EU — single-phase low-voltage hybrid, 220/230 V,
# 50/60 Hz. One of the cheap hybrids that is actually on sale in the Philippines.
# Source: deyeinverter.com, product page for the SUN-3/3.6/5/6K-SG04LP1-EU.
DEYE_SG04 = "https://www.deyeinverter.com/product/single-phase-low-voltage-hybrid-inverter/sun3-3-6-5-6ksg04lp1-3-6kw-single-phase.html"

INVERTERS = [
    # model,          rated kW, max PV kW, Voc max, I max, Isc max, MPPT low/high, MPPT count
    ("SUN-3K-SG04LP1-EU", 3.0, 6.0, 500, 18, 27, 150, 425, 1),
    ("SUN-3.6K-SG04LP1-EU", 3.6, 7.2, 500, 18, 27, 150, 425, 1),
    ("SUN-5K-SG04LP1-EU", 5.0, 10.0, 500, 18, 27, 150, 425, 2),
    ("SUN-6K-SG04LP1-EU", 6.0, 12.0, 500, 18, 27, 150, 425, 2),
]

def inverter_records() -> list[dict]:
    out = []
    for name, ac, pv, vmax, imax, iscmax, low, high, mppt in INVERTERS:
        out.append({
            "inverter_id": "deye-" + re.sub(r"[^a-z0-9]+", "-", name.lower()),
            "name": f"Deye {name}",
            "short_name": f"Deye {name.split('-', 1)[1]}",
            "manufacturer": "Deye",
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
            "battery_comm_family": "Deye LV BMS (self-adaption to BMS)",
            "max_parallel_units": 16,
            "ac_voltage_v": 230,
            "source": DEYE_SG04,
        })
    return out

# Batteries. The app needs nominal_capacity_kwh and the voltage window. Both are
# in the manufacturer's datasheet, not in any open list. Fill from a datasheet —
# do not type these from memory, because the app does electrical checks with them.
BATTERIES: list[dict] = []

# Shops. The app shows the cheapest offer per part. Replace with real suppliers,
# then put the prices in LISTINGS.
SUPPLIERS: list[dict] = []

# One row per part per shop: what it costs and how many are listed.
#   {"component_type": "panel"|"inverter"|"battery", "component_id": "...",
#    "supplier_id": "...", "unit_price_php": 0.0, "stock_units": 0}
# Every price needs a shop and a date. See README.md.
LISTINGS: list[dict] = []


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


def panels(offline: bool):
    out, dropped = [], {"make": 0, "small": 0, "odd": 0}
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
        out.append({
            "panel_id": "cec-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:40],
            "name": name,
            "short_name": short_name(name, maker),
            "manufacturer": maker,
            "rated_power_w": round(power, 1),
            "voc_v": round(voc, 3),
            "vmp_v": round(vmp, 3),
            "imp_a": round(imp, 3),
            "isc_a": round(isc, 3),
            "source": "CEC Modules (NREL SAM)",
        })
    out.sort(key=lambda p: (-p["rated_power_w"], p["short_name"].lower()))
    return out, dropped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    panel_list, dropped = panels(args.offline)
    inverter_list = inverter_records()

    catalog = {
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Panels: CEC Modules, published by NREL. Inverters: manufacturer pages.",
        "counts": {
            "panels": len(panel_list),
            "inverters": len(inverter_list),
            "batteries": len(BATTERIES),
        },
        "suppliers": SUPPLIERS,
        "panels": panel_list,
        "inverters": inverter_list,
        "batteries": BATTERIES,
        "listings": LISTINGS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")

    print(f"wrote {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
    print(f"  panels      {len(panel_list):>6,}   "
          f"dropped {dropped['make']:,} other makes, {dropped['small']:,} small, "
          f"{dropped['odd']:,} unusable")
    print(f"  inverters   {len(inverter_list):>6,}   Deye SG04LP1-EU, 220/230 V, 50/60 Hz")
    print(f"  batteries   {len(BATTERIES):>6,}   <-- needs datasheets")
    print(f"  suppliers   {len(SUPPLIERS):>6,}   <-- needs Philippine shops")
    print(f"  listings    {len(LISTINGS):>6,}   <-- needs prices")
    print()
    print("The app's budget check needs prices, and its backup check needs batteries.")
    print("Both come from outside this script. See catalog/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
