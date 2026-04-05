from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from e1300.nfl import SupportFamily, nfl_kpa
from e1300.tables import (
    gtf_double_ig,
    gtf_monolithic_or_lg,
    gtf_triple_ig,
    lsf_double_long_mo_lg,
    lsf_double_short,
    minimum_thickness_mm,
    triple_lsf,
)

GlassType = Literal["AN", "HS", "FT"]
Construction = Literal["monolithic", "laminated"]


@dataclass(frozen=True)
class LiteSpec:
    nominal_key: str
    glass: GlassType
    construction: Construction


def governing_load_resistance_single(
    short_m: float,
    long_m: float,
    lite: LiteSpec,
    duration: Literal["short", "long"],
    support_family: SupportFamily,
) -> float:
    """Section 7.2.1–7.2.8: LR = NFL × GTF (single lite)."""
    n = nfl_kpa(
        short_m,
        long_m,
        lite.nominal_key,
        construction=lite.construction,
        support_family=support_family,
    )
    gtf = gtf_monolithic_or_lg(lite.glass, duration)
    return n * gtf


def _lsf_double(
    lite1: LiteSpec,
    lite2: LiteSpec,
    duration: Literal["short", "long"],
) -> tuple[float, float]:
    """Table 5 (MO/MO, LG/LG, or short MO/LG) or Table 6 (long MO+LG)."""
    n1, n2 = lite1.nominal_key, lite2.nominal_key
    if duration == "long" and (
        (lite1.construction == "monolithic" and lite2.construction == "laminated")
        or (lite1.construction == "laminated" and lite2.construction == "monolithic")
    ):
        # Table 6: row = MO nominal, col = LG nominal (Lite No. 1 MO, Lite No. 2 LG)
        if lite1.construction == "monolithic":
            return lsf_double_long_mo_lg(n1, n2)
        lsf_mo_row, lsf_lg_col = lsf_double_long_mo_lg(n2, n1)
        return lsf_lg_col, lsf_mo_row
    return lsf_double_short(n1, n2)


def governing_load_resistance_double_ig(
    short_m: float,
    long_m: float,
    lite1: LiteSpec,
    lite2: LiteSpec,
    support_family: SupportFamily,
    *,
    duration: Literal["short", "long"],
) -> tuple[float, dict[str, float]]:
    """
    Section 7.2.9–7.2.13. For long-duration MO+MO uses long branch only; for long-duration
    MO+LG or LG+LG uses the minimum of short- and long-branch lite LRs (7.2.12.6 / 7.2.13.6).
    """
    nfl1 = nfl_kpa(
        short_m,
        long_m,
        lite1.nominal_key,
        construction=lite1.construction,
        support_family=support_family,
    )
    nfl2 = nfl_kpa(
        short_m,
        long_m,
        lite2.nominal_key,
        construction=lite2.construction,
        support_family=support_family,
    )

    def branch(dur: Literal["short", "long"]) -> tuple[float, float, float, float]:
        g1, g2 = gtf_double_ig(lite1.glass, lite2.glass, dur)
        l1, l2 = _lsf_double(lite1, lite2, dur)
        lr1 = nfl1 * g1 / l1
        lr2 = nfl2 * g2 / l2
        return lr1, lr2, g1, g2

    lr1s, lr2s, g1s, g2s = branch("short")
    unit_short = min(lr1s, lr2s)
    ls_s = lsf_double_short(lite1.nominal_key, lite2.nominal_key)

    if duration == "short":
        details = {
            "NFL1": nfl1,
            "NFL2": nfl2,
            "GTF1_short": g1s,
            "GTF2_short": g2s,
            "LSF1": ls_s[0],
            "LSF2": ls_s[1],
            "LR1": lr1s,
            "LR2": lr2s,
            "LR_unit": unit_short,
        }
        return unit_short, details

    lr1l, lr2l, g1l, g2l = branch("long")
    unit_long = min(lr1l, lr2l)
    ls_l = _lsf_double(lite1, lite2, "long")
    mo_mo = (
        lite1.construction == "monolithic" and lite2.construction == "monolithic"
    )
    if mo_mo:
        g = unit_long
    else:
        g = min(unit_short, unit_long)

    details = {
        "NFL1": nfl1,
        "NFL2": nfl2,
        "GTF1_short": g1s,
        "GTF2_short": g2s,
        "GTF1_long": g1l,
        "GTF2_long": g2l,
        "LSF1_short": ls_s[0],
        "LSF2_short": ls_s[1],
        "LSF1_long": ls_l[0],
        "LSF2_long": ls_l[1],
        "LR1_short": lr1s,
        "LR2_short": lr2s,
        "LR1_long": lr1l,
        "LR2_long": lr2l,
        "LR_unit_short": unit_short,
        "LR_unit_long": unit_long,
        "LR_unit": g,
    }
    return g, details


def governing_load_resistance_triple_ig(
    short_m: float,
    long_m: float,
    lite1: LiteSpec,
    lite2: LiteSpec,
    lite3: LiteSpec,
    support_family: SupportFamily,
    duration: Literal["short", "long"] = "short",
) -> tuple[float, dict[str, float]]:
    """Section 7.2.14 — triple IG; Table 7 GTF requires equal glass type for all lites."""
    if not (lite1.glass == lite2.glass == lite3.glass):
        raise ValueError("Table 7 triple-IG GTF requires equal glass type on all three lites.")
    nfl1 = nfl_kpa(
        short_m,
        long_m,
        lite1.nominal_key,
        construction=lite1.construction,
        support_family=support_family,
    )
    nfl2 = nfl_kpa(
        short_m,
        long_m,
        lite2.nominal_key,
        construction=lite2.construction,
        support_family=support_family,
    )
    nfl3 = nfl_kpa(
        short_m,
        long_m,
        lite3.nominal_key,
        construction=lite3.construction,
        support_family=support_family,
    )
    t1 = minimum_thickness_mm(lite1.nominal_key)
    t2 = minimum_thickness_mm(lite2.nominal_key)
    t3 = minimum_thickness_mm(lite3.nominal_key)
    l1, l2, l3 = triple_lsf(t1, t2, t3)
    gtf = gtf_triple_ig(lite1.glass, duration)
    # Table 7 assumes same glass type for all lites; use lite1's type
    lr1 = nfl1 * gtf / l1
    lr2 = nfl2 * gtf / l2
    lr3 = nfl3 * gtf / l3
    g = min(lr1, lr2, lr3)
    details = {
        "NFL1": nfl1,
        "NFL2": nfl2,
        "NFL3": nfl3,
        "GTF": gtf,
        "LSF1": l1,
        "LSF2": l2,
        "LSF3": l3,
        "LR1": lr1,
        "LR2": lr2,
        "LR3": lr3,
    }
    return g, details


