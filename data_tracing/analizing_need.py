import pandas as pd

# Load dataset
file_path = "data/people-without-electricity-country.csv"
df = pd.read_csv(file_path)

# Normalize column names
df = df.rename(columns={'Number of people without access to electricity': 'deficit_population'})

# Filter out regional aggregates and non-country entities.
# Two aggregate families exist in this file, and both must be excluded:
#   OWID_*  -> World, EU (27), income groups, Channel Islands, Kosovo
#   WB_*    -> World Bank regions (WB_SSA, WB_EAP, WB_ECA, WB_LAC, WB_MENAP, WB_NA, WB_SA)
# Excluding only OWID_* let "Sub-Saharan Africa (WB)" rank first as if it were a
# country, inflating the top-15 total by 131 % (~600 M people double-counted).
# Note: df['Code'].notna() was also a no-op — the Code column has no nulls.
clean_df = df[~df['Code'].str.startswith(('OWID_', 'WB_'))].copy()

# Extract the most recent data point for each country
idx_latest = clean_df.groupby('Code')['Year'].idxmax()
latest_per_country = clean_df.loc[idx_latest].copy()

# Sort by absolute deficit in descending order
top_countries = latest_per_country.sort_values(by='deficit_population', ascending=False).head(15)

# Output formatted ranking
print(f"\n{'Country':<32} {'Code':<6} {'Latest Year':<12} {'Deficit (Population)':>22}")
print("=" * 74)

for _, row in top_countries.iterrows():
    country = row['Entity']
    code = row['Code']
    year = int(row['Year'])
    deficit = f"{int(row['deficit_population']):,}".replace(",", " ")
    print(f"{country:<32} {code:<6} {year:<12} {deficit:>22}")
