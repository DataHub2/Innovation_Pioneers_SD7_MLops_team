#!/usr/bin/env python3
"""Corrected version of data_tracing/analizing_need.py.

The original only excluded `OWID_*` codes. Seven World Bank regional aggregates
(`WB_SSA`, `WB_EAP`, `WB_ECA`, `WB_LAC`, `WB_MENAP`, `WB_NA`, `WB_SA`) slipped
through, so "Sub-Saharan Africa (WB)" ranked first and inflated the top-15 total
by 131 %. This version excludes both aggregate families and also reports the
year each country's figure comes from, because a ranking across different years
is not a ranking.

Run from the repository root:

    python data/eda_insights/scripts/fixed_analizing_need.py
"""

from __future__ import annotations

import pandas as pd

FILE_PATH = "data/people-without-electricity-country.csv"
AGGREGATE_PREFIXES = ("OWID_", "WB_")

df = pd.read_csv(FILE_PATH)
df = df.rename(
    columns={"Number of people without access to electricity": "deficit_population"}
)

# FIX: exclude every aggregate family, not just OWID_.
# Replaces: df['Code'].notna() & ~df['Code'].str.startswith('OWID')
# `Code` has no nulls in this file, so the notna() test was a no-op too.
is_aggregate = df["Code"].str.startswith(AGGREGATE_PREFIXES)
excluded = df.loc[is_aggregate, "Entity"].nunique()
clean_df = df.loc[~is_aggregate].copy()

# Latest observation per country.
latest = clean_df.loc[clean_df.groupby("Code")["Year"].idxmax()].copy()
top = latest.sort_values("deficit_population", ascending=False).head(15)

print(f"excluded {excluded} aggregate entities (OWID_* and WB_*)")
print(
    f"\n{'#':<3} {'Country':<32} {'Code':<6} {'Year':<6} {'Deficit (population)':>22}"
)
print("=" * 74)
for rank, (_, row) in enumerate(top.iterrows(), start=1):
    deficit = f"{int(row['deficit_population']):,}".replace(",", " ")
    print(
        f"{rank:<3} {row['Entity']:<32} {row['Code']:<6} "
        f"{int(row['Year']):<6} {deficit:>22}"
    )
print("=" * 74)
print(f"top-15 total: {int(top['deficit_population'].sum()):,} people".replace(",", " "))
