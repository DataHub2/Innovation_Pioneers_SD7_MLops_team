#!/usr/bin/env python3
"""Fetches the country -> World Bank region / income mapping.

    python3 data/eda_insights/scripts/fetch_regions.py

Writes data/eda_insights/country_regions.csv. That file is an INPUT to
build_dashboard.py, which validates it against the regional aggregates already
carried in people-without-electricity-country.csv before it will draw anything.

Source: World Bank country API, https://api.worldbank.org/v2/country?format=json
The API currently classifies by *present-day* income level; the dataset's own
OWID_LIC/LMC/UMC/HIC rows are historical, which is why the low-income check in
build_dashboard.py is allowed a wider tolerance than the regional ones.
"""

from __future__ import annotations

import csv
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "people-without-electricity-country.csv"
OUT = ROOT / "data" / "eda_insights" / "country_regions.csv"
API = "https://api.worldbank.org/v2/country?format=json&per_page=400"


def get() -> list:
    """urllib first; fall back to curl when the local Python lacks a CA bundle."""
    try:
        with urllib.request.urlopen(API, timeout=60) as r:
            return json.load(r)[1]
    except Exception as exc:  # noqa: BLE001 - any transport failure falls back
        print(f"urllib failed ({exc.__class__.__name__}), retrying with curl")
        out = subprocess.run(["curl", "-sS", "--max-time", "60", API],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)[1]


def main() -> None:
    payload = get()
    region = {c["id"]: c["region"]["value"].strip() for c in payload}
    income = {c["id"]: c["incomeLevel"]["value"].strip() for c in payload}

    rows, seen = [], set()
    with SRC.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            code, name = rec["Code"], rec["Entity"]
            if "_" in code or code in seen:  # skip aggregates and duplicates
                continue
            seen.add(code)
            rows.append({
                "Code": code,
                "Entity": name,
                "wb_region": region.get(code, "NOT IN WORLD BANK API"),
                "income_level": income.get(code, "NOT IN WORLD BANK API"),
            })

    rows.sort(key=lambda r: r["Entity"])
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["Code", "Entity", "wb_region", "income_level"])
        w.writeheader()
        w.writerows(rows)
    missing = [r["Code"] for r in rows if r["wb_region"].startswith("NOT IN")]
    print(f"wrote {OUT} ({len(rows)} countries)")
    print(f"no World Bank classification: {missing or 'none'}")


if __name__ == "__main__":
    main()
