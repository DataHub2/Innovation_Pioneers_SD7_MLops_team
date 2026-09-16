# Need-based allocation of local solar energy

An algorithm that decides which loads in a village receive power when the solar
panels cannot cover everyone. The contribution is not a tariff and not a queue —
it is a **load ladder**: need is broken down into individual loads, every load is
placed on a tier, and the tiers are filled from the bottom up. A household can
never take energy from a vaccine cold chain, because they sit on different tiers
and never compete.

Read `docs/METHOD.md` for the method, the evidence and the limitations.
Read `docs/ALLOCATION_CONTRACT.md` for the interface to the dashboard, data
pipeline and hardware.

## The core, in four lines

1. Fill the tiers from the bottom up: life and health → basic need → productive
   → comfort.
2. On each tier: non-shiftable loads first, shiftable loads from solar surplus.
3. Within each group: weighted max-min fairness. Nobody receives zero while
   someone else receives more than they need.
4. Tiers 3 and 4 may not drain the battery. Comfort must not drink the energy
   the night needs.

## Results (same village, same weather, only a different allocation)

| Policy | Critical power delivered | Unserved critical load |
|---|---|---|
| **Load ladder (ours)** | **89.9 %** | **9.2 kWh** |
| Equal per property | 33.2 % | 64.4 kWh |
| First come, first served | 49.8 % | 54.2 kWh |
| Max-min without a ladder | 53.8 % | 50.6 kWh |

Life-critical load is 5.5 % of the village's demand. Comfort is 46 %. Our
algorithm sacrifices comfort to protect what saves lives — the baselines do the
opposite.

**All figures above come from a test fixture, not from field data.** What has to
be replaced is listed in `docs/METHOD.md` section 8. The one set of figures that
is externally verified is the scale case in section 8.2: 98.0 % electricity
access in the Philippines in 2023, implying about 2.3 million people without
access, and 91.6 % global access, implying about 677 million. Source: World Bank
open API, indicator `EG.ELC.ACCS.ZS` (SDG 7.1.1, ESMAP).

## Run

```bash
python -m pytest -q                                # 57 tests: invariants + stress
python -m harness.cli --days 3 --sample            # compare against the baselines
python -m harness.cli --days 3 --json out.json     # JSON for a dashboard
python -m harness.cli --kwp 20 --battery 80 --cloud 0.4,0.3,0.35   # four cloudy days
```

Requires Python 3.11+ and the standard library only.

## Structure

```
allocator/     the algorithm. A pure function: no I/O, no clock, no state.
  models.py      loads, properties, request, result
  config.py      everything that is a value judgement — owned by the village
  fairness.py    weighted max-min fairness, O(n log n)
  policy.py      the load ladder, the reserve rule, credits, reason codes
  baselines.py   three comparison policies to beat
harness/       test fixture. Owns battery physics, load profiles and accounting.
tests/         57 tests: I1-I10 (invariants) and S1-S13 (stress)
docs/          method and interface
```

## Responsibility boundary

The algorithm takes in numbers and hands back numbers plus reasons. It knows
nothing about dashboards, meters, relays or weather forecasts. That is
deliberate: it can be replaced, tested and moved without anything else changing.
