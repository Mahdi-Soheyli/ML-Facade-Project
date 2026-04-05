"""
Surrogate NFL (kPa) surfaces calibrated to Annex A3 anchor points.

Charts in Annex A1 are the authoritative graphical method; this module provides
a smooth calibrated surrogate for dataset generation (see DATASET.md).
"""

from __future__ import annotations

import math
from typing import Literal

from e1300.tables import support_scale

Construction = Literal["monolithic", "laminated"]

SupportFamily = Literal[
    "monolithic_four_sides",
    "laminated_four_sides",
    "monolithic_three_sides",
    "laminated_three_sides",
    "monolithic_two_sides",
    "laminated_two_sides",
    "monolithic_one_side",
    "laminated_one_side",
]

_A0 = 0.07960194676921414
_B_AR = -2.0140287884218178


def _base_nfl(short_m: float, long_m: float, h_mm: float) -> float:
    s = min(short_m, long_m)
    l = max(short_m, long_m)
    area = s * l
    ar = l / s if s > 0 else 1.0
    return float(_A0 * (h_mm**2) / area * math.exp(-_B_AR * (ar - 1.0)))


def _nominal_mm(nominal_key: str) -> float:
    if nominal_key == "2.0_picture":
        return 2.0
    if nominal_key == "2.7_lami":
        return 2.7
    return float(nominal_key.replace("_lami", ""))


def _calib_mono_scalar(h_mm: float) -> float:
    """Scalar multipliers for nominal thicknesses (Annex A3)."""
    cal = {
        2.5: 0.88 / _base_nfl(1.0, 1.5, 2.5),
        3.0: 1.34 / _base_nfl(1.0, 1.5, 3.0),
        6.35: 2.4 / _base_nfl(1.27, 1.524, 6.35),
    }
    keys = sorted(cal.keys())
    if h_mm in cal:
        return cal[h_mm]
    below = [k for k in keys if k <= h_mm]
    above = [k for k in keys if k >= h_mm]
    if not below:
        return cal[keys[0]]
    if not above:
        return cal[keys[-1]]
    h0 = max(below)
    h1 = min(above)
    if h0 == h1:
        return cal[h0]
    t = (h_mm - h0) / (h1 - h0)
    return cal[h0] + t * (cal[h1] - cal[h0])


def _calib_mono_area(h_mm: float, short_m: float, long_m: float) -> float:
    """
    6 mm monolithic: two-point calibration in 1/A so Ex1 and Ex3 NFL match charts.
    Other thicknesses: scalar calibration on reference geometry (1.0 x 1.5 m).
    """
    if abs(h_mm - 6.0) > 0.001:
        return _calib_mono_scalar(h_mm)
    s = min(short_m, long_m)
    l = max(short_m, long_m)
    a = s * l
    b1 = _base_nfl(1.2, 1.5, 6.0)
    b2 = _base_nfl(1.52, 1.9, 6.0)
    a1, a2 = 1.2 * 1.5, 1.52 * 1.9
    k1, k2 = b1 / a1, b2 / a2
    det = b1 * k2 - b2 * k1
    if abs(det) < 1e-18:
        return _calib_mono_scalar(h_mm)
    c0 = (2.5 * k2 - 1.8 * k1) / det
    c1 = (b1 * 1.8 - b2 * 2.5) / det
    return float(c0 + c1 / a)


def _calib_lami(h_mm: float, _short_m: float, _long_m: float) -> float:
    """
    LG: NFL(s,l,h) = 2.5 kPa * base(s,l,h) / base(1.52m, 1.9m, h) (Annex A3 Ex3 anchor).
    """
    ref = _base_nfl(1.52, 1.9, h_mm)
    return (2.5 / ref) if ref > 0 else 1.0


def nfl_kpa(
    short_m: float,
    long_m: float,
    nominal_key: str,
    *,
    construction: Construction,
    support_family: SupportFamily,
) -> float:
    """
    Non-factored load (kPa) for Pb <= 0.008 (surrogate, Annex A1).

    short_m, long_m: rectangle edges in metres.
    nominal_key: Table 4 key e.g. '6', '2.7_lami', '2.0_picture'.
    """
    if short_m <= 0 or long_m <= 0:
        raise ValueError("Dimensions must be positive")

    h_mm = _nominal_mm(nominal_key)
    base = _base_nfl(short_m, long_m, h_mm)
    if construction == "monolithic":
        cal = (
            _calib_mono_area(h_mm, short_m, long_m)
            if abs(h_mm - 6.0) < 0.001
            else _calib_mono_scalar(h_mm)
        )
    else:
        cal = _calib_lami(h_mm, short_m, long_m)
    raw = base * cal
    raw = max(0.05, min(15.0, raw))
    raw *= support_scale(support_family)
    return float(raw)
