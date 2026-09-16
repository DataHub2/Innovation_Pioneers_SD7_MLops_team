"""Test fixture and evaluation. Owns battery physics, load profiles and energy
accounting — everything that sits outside the algorithm."""

from .scenario import LoadSpec, PropertySpec, build_barangay, solar_kw
from .simulate import SimConfig, SimResult, Simulator, run_comparison

__all__ = [
    "LoadSpec",
    "PropertySpec",
    "SimConfig",
    "SimResult",
    "Simulator",
    "build_barangay",
    "run_comparison",
    "solar_kw",
]
