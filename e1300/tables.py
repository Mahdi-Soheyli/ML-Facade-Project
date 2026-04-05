from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

GlassType = Literal["AN", "HS", "FT"]

Duration = Literal["short", "long"]


@lru_cache(maxsize=1)
def _tables() -> dict[str, Any]:
    from e1300.paths import data_path

    with open(data_path("tables.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _lsf5() -> dict[str, Any]:
    from e1300.paths import data_path

    with open(data_path("lsf_table5.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _lsf6() -> dict[str, Any]:
    from e1300.paths import data_path

    with open(data_path("lsf_table6.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _chart_catalog() -> dict[str, Any]:
    from e1300.paths import data_path

    with open(data_path("chart_catalog.json"), encoding="utf-8") as f:
        return json.load(f)


def minimum_thickness_mm(nominal_key: str) -> float:
    t = _tables()["table4_nominal_mm_to_minimum_mm"]
    if nominal_key not in t:
        raise KeyError(f"Unknown nominal key: {nominal_key}")
    return float(t[nominal_key])


def gtf_monolithic_or_lg(glass: GlassType, duration: Duration) -> float:
    row = _tables()["gtf_table1_monolithic_or_lg"][glass]
    return float(row["short" if duration == "short" else "long"])


def gtf_double_ig(
    g1: GlassType, g2: GlassType, duration: Duration
) -> tuple[float, float]:
    if duration == "short":
        t = _tables()["gtf_table2_ig_short"]
    else:
        t = _tables()["gtf_table3_ig_long"]
    pair = t[g1][g2]
    return float(pair[0]), float(pair[1])


def gtf_triple_ig(glass: GlassType, duration: Duration) -> float:
    row = _tables()["gtf_table7_triple_ig"][glass]
    return float(row["short" if duration == "short" else "long"])


def lsf_double_short(nominal_1: str, nominal_2: str) -> tuple[float, float]:
    row = _lsf5()[nominal_1][nominal_2]
    return float(row["lsf1"]), float(row["lsf2"])


def lsf_double_long_mo_lg(nominal_mo: str, nominal_lg: str) -> tuple[float, float]:
    """Table 6: Lite 1 MO, Lite 2 LG, long duration only."""
    row = _lsf6()[nominal_mo][nominal_lg]
    return float(row["lsf1"]), float(row["lsf2"])


def triple_lsf(
    t1_mm: float, t2_mm: float, t3_mm: float
) -> tuple[float, float, float]:
    """Eqs (6)-(8) Section 7.2.14 — minimum thicknesses from Table 4."""
    a, b, c = t1_mm**3, t2_mm**3, t3_mm**3
    s = a + b + c
    return a / s, b / s, c / s


def support_scale(family: str) -> float:
    cat = _chart_catalog()
    return float(cat["support_family_scale"].get(family, 1.0))
