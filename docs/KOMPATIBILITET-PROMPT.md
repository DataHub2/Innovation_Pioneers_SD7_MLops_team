# Compatibility prompt

Paste everything below into an LLM. It gives the model the hardware, the exact
rules the app applies, and asks for a combination matrix.

Two things to know before reading the answer:

* The app places **all panels in ONE series string on ONE MPPT**. That is a
  deliberate demo simplification, and it makes the app stricter than reality:
  a real design splits panels across strings and MPPTs. Ask the model for the
  real answer too, and expect it to differ.
* The app checks 10 technical things plus budget. Panels are checked at STC
  (25 degrees C). Voc rises as temperature falls, so a string that passes here
  can still exceed the inverter's DC limit on a cold morning.

---

```
You are checking whether solar hardware can be combined. Be precise, show the
arithmetic, and say plainly when something does not fit.

## Hardware

INVERTERS
| inverter_id              | name                     | kW  | max_pv_kW | mppt_min_v | mppt_max_v | max_dc_v | max_imp_a | max_isc_a | mppt_count | batt_min_v | batt_max_v | bms_family  |
|--------------------------|--------------------------|-----|-----------|------------|------------|----------|-----------|-----------|------------|------------|------------|-------------|
| deye-sun-3k-sg04lp1-eu   | Deye SUN-3K-SG04LP1-EU   | 3.0 | 6.0       | 150        | 425        | 500      | 18        | 27        | 1          | 40         | 60         | Deye LV BMS |
| deye-sun-3-6k-sg04lp1-eu | Deye SUN-3.6K-SG04LP1-EU | 3.6 | 7.2       | 150        | 425        | 500      | 18        | 27        | 1          | 40         | 60         | Deye LV BMS |
| deye-sun-5k-sg04lp1-eu   | Deye SUN-5K-SG04LP1-EU   | 5.0 | 10.0      | 150        | 425        | 500      | 18        | 27        | 2          | 40         | 60         | Deye LV BMS |
| deye-sun-6k-sg04lp1-eu   | Deye SUN-6K-SG04LP1-EU   | 6.0 | 12.0      | 150        | 425        | 500      | 18        | 27        | 2          | 40         | 60         | Deye LV BMS |

BATTERY
| battery_id    | name          | nominal_kwh | min_v | max_v | max_parallel_units | bms_family  |
|---------------|---------------|-------------|-------|-------|--------------------|-------------|
| deye-rw-f10-2 | Deye RW-F10.2 | 10.2        | 43.2  | 57.6  | 32                 | Deye LV BMS |

PANELS
| panel_id                                                 | rated_W | vmp_v | imp_a | voc_v | isc_a |
|----------------------------------------------------------|---------|-------|-------|-------|-------|
| cec-rec-group-rec740aa-pro-xl                            | 740     | 46.3  | 15.97 | 53.8  | 16.75 |
| cec-trina-solar-tsm-740neg21c20                          | 740     | 42.1  | 17.58 | 50.3  | 18.66 |
| cec-trina-solar-tsm-735neg21c20                          | 735     | 41.9  | 17.55 | 50.1  | 18.62 |
| cec-rec-group-rec730aa-pro-xl                            | 730     | 46.3  | 15.79 | 53.7  | 16.57 |
| cec-risen-energy-co-ltd-rsm132-8-730bhdg                 | 730     | 42.2  | 17.32 | 50.33 | 18.38 |
| cec-suzhou-talesun-solar-technologies-co-ltd-tm8g66m-730 | 730     | 41.7  | 17.51 | 49.8  | 18.57 |
| cec-trina-solar-tsm-730neg21c20                          | 730     | 41.7  | 17.51 | 49.9  | 18.58 |
| cec-risen-energy-co-ltd-rsm132-8-725bhdg                 | 725     | 42.14 | 17.23 | 50.26 | 18.29 |
| cec-suzhou-talesun-solar-technologies-co-ltd-tm8g66m-725 | 725     | 41.5  | 17.47 | 49.6  | 18.53 |
| cec-trina-solar-coltd-tsm-725neg21c20                    | 725     | 41.5  | 17.47 | 49.6  | 18.54 |
| cec-rec-group-rec720aa-pro-xl                            | 720     | 46.2  | 15.6  | 53.6  | 16.39 |
| cec-risen-energy-co-ltd-rsm132-8-720bhdg                 | 720     | 42.08 | 17.13 | 50.18 | 18.19 |
| cec-suzhou-talesun-solar-technologies-co-ltd-tm8g66m-720 | 720     | 41.3  | 17.44 | 49.4  | 18.49 |
| cec-trina-solar-coltd-tsm-720neg21c20                    | 720     | 41.3  | 17.44 | 49.4  | 18.49 |
| cec-risen-energy-co-ltd-rsm132-8-715bhdg                 | 715     | 42.01 | 17.03 | 50.09 | 18.08 |
| cec-suzhou-talesun-solar-technologies-co-ltd-tm8g66m-715 | 715     | 41.1  | 17.4  | 49.2  | 18.44 |
| cec-trina-solar-coltd-tsm-715neg21c20                    | 715     | 41.1  | 17.4  | 49.2  | 18.44 |
| cec-risen-energy-co-ltd-rsm132-8-710bhdg                 | 710     | 41.93 | 16.95 | 50.01 | 18.0  |
| cec-suzhou-talesun-solar-technologies-co-ltd-tm8g66m-710 | 710     | 40.9  | 17.36 | 49.0  | 18.4  |
| cec-trina-solar-coltd-tsm-710neg21c20                    | 710     | 40.9  | 17.36 | 49.0  | 18.4  |
| cec-risen-energy-co-ltd-rsm132-8-705bhdg                 | 705     | 41.86 | 16.86 | 49.92 | 17.91 |
| cec-suzhou-talesun-solar-technologies-co-ltd-tm8g66m-705 | 705     | 40.7  | 17.33 | 48.8  | 18.36 |
| cec-trina-solar-coltd-tsm-705neg21c20                    | 705     | 40.7  | 17.33 | 48.8  | 18.36 |
| cec-risen-energy-co-ltd-rsm132-8-700bhdg                 | 700     | 41.78 | 16.77 | 49.83 | 17.82 |
| cec-trina-solar-coltd-tsm-700neg21c20                    | 700     | 40.5  | 17.29 | 48.6  | 18.32 |
| cec-risen-energy-co-ltd-rsm132-8-695bhdg                 | 695     | 41.71 | 16.68 | 49.74 | 17.74 |
| cec-trina-solar-coltd-tsm-695neg21c20                    | 695     | 40.3  | 17.25 | 48.3  | 18.28 |
| cec-risen-energy-co-ltd-rsm132-8-690bhdg                 | 690     | 41.63 | 16.6  | 49.65 | 17.66 |
| cec-trina-solar-coltd-tsm-690neg21c20                    | 690     | 40.1  | 17.23 | 47.9  | 18.25 |
| cec-risen-energy-co-ltd-rsm132-8-685bhdg                 | 685     | 41.56 | 16.5  | 49.56 | 17.56 |
| cec-trina-solar-coltd-tsm-685neg21c20                    | 685     | 39.8  | 17.19 | 47.7  | 18.21 |
| cec-rec-group-rec680aa-pro-l                             | 680     | 42.6  | 16.01 | 49.3  | 16.76 |
| cec-risen-energy-co-ltd-rsm132-8-680bhdg                 | 680     | 41.48 | 16.41 | 49.47 | 17.48 |
| cec-trina-solar-coltd-tsm-680neg21c20                    | 680     | 39.6  | 17.16 | 47.4  | 18.18 |
| cec-risen-energy-co-ltd-rsm132-8-675bhdg                 | 675     | 41.41 | 16.32 | 49.38 | 17.4  |
| cec-trina-solar-coltd-tsm-675neg21c20                    | 675     | 39.4  | 17.12 | 47.2  | 18.14 |
| cec-rec-group-rec670aa-pro-l                             | 670     | 42.5  | 15.79 | 49.2  | 16.55 |
| cec-risen-energy-co-ltd-rsm132-8-670bhdg                 | 670     | 41.33 | 16.23 | 49.29 | 17.31 |
| cec-risen-energy-co-ltd-rsm132-8-670bmdg                 | 670     | 38.59 | 17.37 | 46.29 | 18.38 |
| cec-risen-energy-co-ltd-rsm132-8-670m                    | 670     | 38.48 | 17.42 | 46.15 | 18.43 |
| cec-trina-solar-tsm-670de21                              | 670     | 38.2  | 17.55 | 46.1  | 18.62 |
| cec-trina-solar-tsm-670deg21c20                          | 670     | 38.5  | 17.43 | 46.3  | 18.55 |
| cec-trina-solar-coltd-tsm-670neg21c20                    | 670     | 39.2  | 17.09 | 47.0  | 18.1  |
| cec-risen-energy-co-ltd-rsm132-8-665bhdg                 | 665     | 41.25 | 16.14 | 49.2  | 17.22 |
| cec-risen-energy-co-ltd-rsm132-8-665bmdg                 | 665     | 38.41 | 17.32 | 46.09 | 18.33 |
| cec-risen-energy-co-ltd-rsm132-8-665m                    | 665     | 38.3  | 17.37 | 45.95 | 18.38 |
| cec-trina-solar-tsm-665de21                              | 665     | 38.0  | 17.51 | 45.9  | 18.57 |
| cec-trina-solar-tsm-665deg21c20                          | 665     | 38.3  | 17.39 | 46.1  | 18.5  |
| cec-trina-solar-coltd-tsm-665neg21c20                    | 665     | 39.0  | 17.06 | 46.8  | 18.07 |
| cec-rec-group-rec660aa-pro-l                             | 660     | 42.4  | 15.6  | 49.2  | 16.35 |
| cec-risen-energy-co-ltd-rsm132-8-660bhdg                 | 660     | 41.18 | 16.05 | 49.11 | 17.14 |
| cec-risen-energy-co-ltd-rsm132-8-660bmdg                 | 660     | 38.23 | 17.27 | 45.89 | 18.28 |
| cec-risen-energy-co-ltd-rsm132-8-660m                    | 660     | 38.12 | 17.32 | 45.75 | 18.33 |
| cec-trina-solar-tsm-660de21                              | 660     | 37.8  | 17.47 | 45.7  | 18.53 |
| cec-trina-solar-tsm-660deg21c20                          | 660     | 38.1  | 17.35 | 45.9  | 18.45 |
| cec-trina-solar-coltd-tsm-660neg21c20                    | 660     | 38.8  | 17.02 | 46.6  | 18.03 |
| cec-risen-energy-co-ltd-rsm132-8-655bhdg                 | 655     | 41.1  | 15.96 | 49.02 | 17.06 |
| cec-risen-energy-co-ltd-rsm132-8-655bmdg                 | 655     | 38.05 | 17.22 | 45.69 | 18.23 |
| cec-risen-energy-co-ltd-rsm132-8-655m                    | 655     | 37.94 | 17.27 | 45.55 | 18.28 |
| cec-trina-solar-tsm-655de21                              | 655     | 37.6  | 17.43 | 45.5  | 18.48 |
| cec-ja-solar-jam72d30-550-mb                             | 550     | 41.96 | 13.11 | 49.9  | 14.0  |

## The rules to apply

A combination is valid only if ALL of these pass.

For a panel, an inverter, and a number of panels n:

1. quantities        n is a positive whole number
2. pv-capacity       n * panel.rated_W / 1000 <= inverter.max_pv_kW
3. vmp               n * panel.vmp_v must be inside inverter.mppt_min_v .. mppt_max_v
4. voc               n * panel.voc_v must be strictly below inverter.max_dc_v
5. current           panel.imp_a <= inverter.max_imp_a
                     AND panel.isc_a <= inverter.max_isc_a
6. mppt-count        the number of MPPT inputs used must not exceed inverter.mppt_count

For the battery and the inverter:

7. battery-voltage   battery.min_v >= inverter.batt_min_v
                     AND battery.max_v <= inverter.batt_max_v
8. bms               battery.bms_family must EQUAL inverter.bms_family
9. battery-count     battery count between 1 and battery.max_parallel_units

## What I want back

A. PANEL MATCHING. For every inverter, give the range of n (1 to 30) for which
   every panel passes all six rules. Present it as one table: one row per
   panel, one column per inverter, and in each cell the valid n range or the
   reason it fails. Say which rule is the binding constraint for each cell.

B. BATTERY MATCHING. For every inverter, say whether the battery passes rules
   7, 8 and 9, and give the maximum battery count.

C. FULLY COMPATIBLE SETS. List, in plain language, every combination of
   (panel x inverter x battery) that passes all nine rules, with the panel
   count range. If nothing passes, say so.

D. WHAT THE SIMPLIFICATION HIDES. The rules above assume one series string on
   one MPPT. Tell me what changes with a realistic design: splitting into
   multiple strings, using both MPPT inputs, and the fact that Voc rises in
   cold weather. For each inverter, give the maximum number of panels per
   string if the coldest expected cell temperature is 5 degrees C, given the
   panel's Voc temperature coefficient (assume -0.25 %/degree C if the panel
   does not state one).

E. THE BINDING LIMIT. For each inverter, name the single specification that
   limits how many panels you can connect, and say whether the limit is the DC
   voltage, the MPPT window, the current, or the panel wattage.

Answer in tables. Do not summarise the input back to me.
```
