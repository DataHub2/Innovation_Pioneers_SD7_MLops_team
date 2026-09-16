"""Test fixture: a synthetic barangay with solar power, a battery and load
profiles.

IMPORTANT: this is *not* the production component. It is a test fixture that
lets the algorithm be developed, stressed and demonstrated before real data
exists. Every number here is an assumption, chosen to be plausible for a rural
Filipino barangay with a small solar installation.

The fixture also owns everything outside the algorithm: battery physics, load
profiles, when households curtail voluntarily, and credit accounting. The
boundary against the algorithm is exactly the one in
docs/ALLOCATION_CONTRACT.md.

Where a number is an assumption, the replacement source is named in
docs/METHOD.md section 8.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from allocator.models import Category, Tier


@dataclass(frozen=True)
class LoadSpec:
    name: str
    tier: Tier
    daily_kwh: float
    window: tuple[float, float] | None = None  # None = 24/7. (start, end) in hours.
    shiftable: bool = False
    #: for shiftable loads: how many cycles the load wants to run during the day
    spread_cycles: int = 1
    deadline: float | None = None


@dataclass(frozen=True)
class PropertySpec:
    id: str
    category: Category
    occupants: int
    vulnerability_flags: frozenset[str]
    loads: tuple[LoadSpec, ...]
    declared_kwh_per_day: float = 0.0
    historical_kwh_per_day: float = 0.0


# ----------------------------------------------------------- load profiles
CLINIC_LOADS = (
    LoadSpec("vaccine_cold_chain", Tier.LIFE_HEALTH, 1.2),
    LoadSpec("emergency_lighting", Tier.LIFE_HEALTH, 0.6, (17, 23)),
    LoadSpec("medical_device_charge", Tier.LIFE_HEALTH, 0.3, (7, 19)),
    LoadSpec("water_sterilizer", Tier.BASIC, 0.8, (6, 12), shiftable=True,
             spread_cycles=4, deadline=12),
    LoadSpec("waiting_room_fan", Tier.COMFORT, 0.9, (8, 17)),
)

WATER_LOADS = (
    LoadSpec("drinking_water_pump", Tier.LIFE_HEALTH, 4.0, (6, 20),
             shiftable=True, spread_cycles=6, deadline=19),
    LoadSpec("irrigation_pump", Tier.PRODUCTIVE, 5.0, (6, 17),
             shiftable=True, spread_cycles=8, deadline=16),
)

SCHOOL_LOADS = (
    LoadSpec("classroom_lighting", Tier.BASIC, 1.5, (7, 17)),
    LoadSpec("computer_lab", Tier.PRODUCTIVE, 2.0, (8, 15),
             shiftable=True, spread_cycles=4, deadline=15),
)

COMMUNITY_LOADS = (
    LoadSpec("street_lighting", Tier.BASIC, 1.8, (18, 5)),
    LoadSpec("charging_station", Tier.COMFORT, 2.5, (9, 17),
             shiftable=True, spread_cycles=4, deadline=16),
)


def _household_loads(rng: random.Random) -> tuple[LoadSpec, ...]:
    loads: list[LoadSpec] = [
        LoadSpec("basic_lighting", Tier.BASIC, 0.35, (18, 23)),
        LoadSpec("phone_charging", Tier.BASIC, 0.08, (18, 23)),
    ]
    if rng.random() < 0.7:
        loads.append(LoadSpec("food_fridge", Tier.BASIC, 1.1))
    if rng.random() < 0.8:
        loads.append(LoadSpec("fan", Tier.BASIC, 0.6, (20, 6)))
    if rng.random() < 0.8:
        loads.append(LoadSpec("tv", Tier.COMFORT, 0.5, (18, 23)))
    if rng.random() < 0.35:
        loads.append(LoadSpec("aircon", Tier.COMFORT, 3.5, (20, 6)))
    if rng.random() < 0.2:
        loads.append(LoadSpec("extra_freezer", Tier.COMFORT, 1.6))
    if rng.random() < 0.15:
        loads.append(
            LoadSpec("ev_tricycle", Tier.COMFORT, 2.2, (9, 17),
                     shiftable=True, spread_cycles=4, deadline=16)
        )
    return tuple(loads)


def build_barangay(
    n_households: int = 24, seed: int = 7
) -> tuple[PropertySpec, ...]:
    """A plausible small barangay: clinic, water pump, school, three productive
    businesses, street lighting and a number of households."""
    rng = random.Random(seed)
    specs: list[PropertySpec] = [
        PropertySpec("clinic", Category.CLINIC, 12, frozenset({"cold_chain"}),
                     CLINIC_LOADS),
        PropertySpec("water_pump", Category.WATER, 1,
                     frozenset({"medical_device"}), WATER_LOADS),
        PropertySpec("school", Category.SCHOOL, 60, frozenset(), SCHOOL_LOADS),
        PropertySpec(
            "ice_maker",
            Category.PRODUCTIVE,
            3,
            frozenset(),
            (LoadSpec("ice_maker", Tier.PRODUCTIVE, 6.0, (8, 16),
                      shiftable=True, spread_cycles=4, deadline=15),),
        ),
        PropertySpec(
            "sari_sari",
            Category.PRODUCTIVE,
            2,
            frozenset(),
            (
                LoadSpec("store_fridge", Tier.PRODUCTIVE, 3.0),
                LoadSpec("store_lighting", Tier.BASIC, 0.5, (18, 23)),
            ),
        ),
        PropertySpec(
            "sewing_shop",
            Category.PRODUCTIVE,
            2,
            frozenset(),
            (LoadSpec("sewing_machine", Tier.PRODUCTIVE, 1.5, (9, 17),
                      shiftable=True, spread_cycles=3, deadline=16),),
        ),
        PropertySpec("street_lights", Category.COMMUNITY, 0, frozenset(),
                     COMMUNITY_LOADS),
    ]

    for i in range(n_households):
        pid = f"hh_{i + 1:02d}"
        occupants = rng.choice((2, 2, 3, 3, 4, 4, 5, 6, 8))
        flags: set[str] = set()
        if i == 3:
            flags.add("dialysis")
        if rng.random() < 0.25:
            flags.add("elderly")
        if rng.random() < 0.2:
            flags.add("infant")
        loads = _household_loads(rng)
        if "dialysis" in flags:
            # A household can carry a critical load. The tier belongs to the
            # load, not to the building.
            loads = (LoadSpec("home_dialysis", Tier.LIFE_HEALTH, 0.9),) + loads
        specs.append(
            PropertySpec(pid, Category.HOUSEHOLD, occupants, frozenset(flags), loads)
        )

    out: list[PropertySpec] = []
    for s in specs:
        daily = sum(l.daily_kwh for l in s.loads)
        out.append(
            replace(
                s,
                declared_kwh_per_day=daily,
                historical_kwh_per_day=daily * rng.uniform(0.9, 1.1),
            )
        )
    return tuple(out)


# ------------------------------------------------------- solar and battery
def solar_kw(hour: float, kwp: float, cloud: float = 1.0) -> float:
    """Simple solar profile: sun between 06:00 and 18:00, cloud factor per day."""
    if hour < 6.0 or hour > 18.0:
        return 0.0
    return kwp * math.sin(math.pi * (hour - 6.0) / 12.0) * max(0.0, cloud)


def in_window(hour: float, window: tuple[float, float] | None) -> bool:
    if window is None:
        return True
    start, end = window
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def cycles_in_window(window: tuple[float, float] | None, cycles_per_day: int) -> int:
    if window is None:
        return cycles_per_day
    start, end = window
    span = (end - start) % 24 or 24.0
    return max(1, int(round(cycles_per_day * span / 24.0)))
