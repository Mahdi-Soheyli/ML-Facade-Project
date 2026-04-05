"""
Logarithmic wind profile (neutral stratification, flat terrain).

Same closed form as documented on wind-data.ch Windprofil tool:
https://wind-data.ch/tools/profile.php

v2 = v1 * ln(h2/z0) / ln(h1/z0), with h > z0.
"""

from __future__ import annotations

import math

from app.schemas import WindParams


def wind_speed_at_height(
    v1_m_s: float,
    h1_m: float,
    h2_m: float,
    z0_m: float,
) -> float:
    if z0_m <= 0:
        raise ValueError("z0 must be positive")
    if h1_m <= z0_m or h2_m <= z0_m:
        raise ValueError("Heights must exceed roughness length z0")
    return float(
        v1_m_s
        * math.log(h2_m / z0_m)
        / math.log(h1_m / z0_m)
    )


def dynamic_pressure_kpa(v_m_s: float, rho: float) -> float:
    """q = 0.5 * rho * v^2 (Pa), returned in kPa."""
    pa = 0.5 * rho * v_m_s**2
    return pa / 1000.0


def design_pressure_kpa(wind: WindParams, elevation_m: float) -> tuple[float, float, float]:
    """
    Returns (v_at_h, q_kpa, design_load_kpa).
    """
    v2 = wind_speed_at_height(wind.v1_m_s, wind.h1_m, max(elevation_m, wind.z0_m + 0.01), wind.z0_m)
    q = dynamic_pressure_kpa(v2, wind.air_density_kg_m3)
    return v2, q, q * wind.pressure_factor
