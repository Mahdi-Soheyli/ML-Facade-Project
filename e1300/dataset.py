"""Build E1300_Research_Dataset.csv from the surrogate oracle."""

from __future__ import annotations

import csv
import itertools
from pathlib import Path

from e1300.lr import (
    LiteSpec,
    governing_load_resistance_double_ig,
    governing_load_resistance_single,
    governing_load_resistance_triple_ig,
)
from e1300.nfl import SupportFamily
from e1300.paths import ROOT

GLASS = ("AN", "HS", "FT")
NOM_MO = ["3", "4", "5", "6", "8", "10", "12", "16", "19"]


def _grid_dims():
    shorts = [0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]
    longs = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0]
    for s in shorts:
        for ell in longs:
            if ell >= s:
                yield s, ell


def build_rows(
    *,
    max_rows: int | None = 8000,
    design_load_kpa: float = 3.0,
    support: SupportFamily = "monolithic_four_sides",
) -> list[dict]:
    rows: list[dict] = []

    def push(row: dict) -> bool:
        rows.append(row)
        return max_rows is not None and len(rows) >= max_rows

    for s, ell in _grid_dims():
        for g, nk in itertools.product(GLASS, NOM_MO):
            lite = LiteSpec(nk, g, "monolithic")  # type: ignore[arg-type]
            lr = governing_load_resistance_single(s, ell, lite, "short", support)
            if push(
                {
                    "case": "single_monolithic",
                    "short_m": s,
                    "long_m": ell,
                    "support_family": support,
                    "lite1_nominal": nk,
                    "lite1_glass": g,
                    "lite1_construction": "monolithic",
                    "duration": "short",
                    "design_load_kpa": design_load_kpa,
                    "governing_LR_kpa": lr,
                    "acceptable": lr >= design_load_kpa,
                }
            ):
                return rows

        for g1, g2, n1, n2 in itertools.product(
            GLASS, GLASS, ["6", "8", "10"], ["6", "8", "10"]
        ):
            a = LiteSpec(n1, g1, "monolithic")
            b = LiteSpec(n2, g2, "monolithic")
            lr, _ = governing_load_resistance_double_ig(
                s, ell, a, b, support, duration="short"
            )
            if push(
                {
                    "case": "double_ig_momo",
                    "short_m": s,
                    "long_m": ell,
                    "support_family": support,
                    "lite1_nominal": n1,
                    "lite1_glass": g1,
                    "lite1_construction": "monolithic",
                    "lite2_nominal": n2,
                    "lite2_glass": g2,
                    "lite2_construction": "monolithic",
                    "duration": "short",
                    "design_load_kpa": design_load_kpa,
                    "governing_LR_kpa": lr,
                    "acceptable": lr >= design_load_kpa,
                }
            ):
                return rows

        for g, n1, n2, n3 in itertools.product(
            GLASS, ["3", "4", "5"], ["2.5", "3", "4"], ["3", "4", "5"]
        ):
            a = LiteSpec(n1, g, "monolithic")
            b = LiteSpec(n2, g, "monolithic")
            c = LiteSpec(n3, g, "monolithic")
            lr, _ = governing_load_resistance_triple_ig(
                s, ell, a, b, c, support, duration="short"
            )
            if push(
                {
                    "case": "triple_ig",
                    "short_m": s,
                    "long_m": ell,
                    "support_family": support,
                    "lite1_nominal": n1,
                    "lite2_nominal": n2,
                    "lite3_nominal": n3,
                    "glass_all": g,
                    "duration": "short",
                    "design_load_kpa": design_load_kpa,
                    "governing_LR_kpa": lr,
                    "acceptable": lr >= design_load_kpa,
                }
            ):
                return rows

        for g1, g2, n1, n2 in itertools.product(
            GLASS, GLASS, ["6", "8"], ["8", "10", "12"]
        ):
            a = LiteSpec(n1, g1, "monolithic")
            b = LiteSpec(n2, g2, "laminated")
            lr, _ = governing_load_resistance_double_ig(
                s, ell, a, b, support, duration="short"
            )
            if push(
                {
                    "case": "double_ig_molg",
                    "short_m": s,
                    "long_m": ell,
                    "support_family": support,
                    "lite1_nominal": n1,
                    "lite1_glass": g1,
                    "lite1_construction": "monolithic",
                    "lite2_nominal": n2,
                    "lite2_glass": g2,
                    "lite2_construction": "laminated",
                    "duration": "short",
                    "design_load_kpa": design_load_kpa,
                    "governing_LR_kpa": lr,
                    "acceptable": lr >= design_load_kpa,
                }
            ):
                return rows

    return rows


def export_csv(path: Path | None = None, **kwargs) -> Path:
    path = path or (ROOT / "E1300_Research_Dataset.csv")
    rows = build_rows(**kwargs)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames: list[str] = sorted({k for row in rows for k in row})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    return path
