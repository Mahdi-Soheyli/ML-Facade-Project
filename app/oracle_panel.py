"""Map API panels to e1300 oracle (LR, minimum nominal search)."""

from __future__ import annotations

import json
from pathlib import Path

from e1300.lr import LiteSpec, governing_load_resistance_double_ig, governing_load_resistance_single, governing_load_resistance_triple_ig
from e1300.nfl import SupportFamily

from app.schemas import LiteInput, PanelInput

_DATA_DIR = Path(__file__).resolve().parents[1] / "building_code" / "e1300_data"


def _nominal_order() -> list[str]:
    with open(_DATA_DIR / "tables.json", encoding="utf-8") as f:
        data = json.load(f)
    return list(data["nominal_keys_ordered"])


def _short_long(panel: PanelInput) -> tuple[float, float]:
    a, b = panel.width_m, panel.height_m
    return (min(a, b), max(a, b))


def _to_spec(lite: LiteInput) -> LiteSpec:
    nk = lite.nominal_key or "6"
    return LiteSpec(nominal_key=nk, glass=lite.glass, construction=lite.construction)


def minimum_nominal_single(
    short_m: float,
    long_m: float,
    glass: str,
    construction: str,
    support: SupportFamily,
    design_load_kpa: float,
    duration: str,
) -> tuple[str, float, bool, dict]:
    """Scan Table 4 order; first nominal with LR >= load."""
    order = _nominal_order()
    for nk in order:
        lite = LiteSpec(nk, glass, construction)  # type: ignore[arg-type]
        lr = governing_load_resistance_single(
            short_m, long_m, lite, duration, support  # type: ignore[arg-type]
        )
        if lr >= design_load_kpa:
            return nk, lr, True, {"scan": "single_monolithic", "first_ok_nominal": nk}
    nk = order[-1]
    lite = LiteSpec(nk, glass, construction)  # type: ignore[arg-type]
    lr = governing_load_resistance_single(
        short_m, long_m, lite, duration, support  # type: ignore[arg-type]
    )
    return nk, lr, False, {"scan": "single_monolithic", "note": "no nominal met load; thickest shown"}


def run_oracle_panel(
    panel: PanelInput,
    design_load_kpa: float,
) -> tuple[float, bool, dict, str | None]:
    """
    Returns governing_LR, acceptable, details, minimum_nominal_key (if searched).
    """
    s, ell = _short_long(panel)
    sup: SupportFamily = panel.support_family  # type: ignore[assignment]
    dur = panel.duration

    if panel.case == "single_monolithic":
        lite_in = panel.lites[0]
        if lite_in.nominal_key is None:
            nk, lr, ok, det = minimum_nominal_single(
                s, ell, lite_in.glass, lite_in.construction, sup, design_load_kpa, dur
            )
            return lr, ok, det, nk
        lite = _to_spec(lite_in)
        lr = governing_load_resistance_single(s, ell, lite, dur, sup)
        ok = lr >= design_load_kpa
        return lr, ok, {"LR_unit": lr}, lite_in.nominal_key

    if panel.case == "double_ig_momo":
        a, b = panel.lites[0], panel.lites[1]
        if a.nominal_key is None:
            a = LiteInput(nominal_key="6", glass=a.glass, construction=a.construction)
        if b.nominal_key is None:
            b = LiteInput(nominal_key="6", glass=b.glass, construction=b.construction)
        l1 = _to_spec(a)
        l2 = _to_spec(b)
        lr, det = governing_load_resistance_double_ig(s, ell, l1, l2, sup, duration=dur)
        ok = lr >= design_load_kpa
        return lr, ok, det, None

    if panel.case == "double_ig_molg":
        a, b = panel.lites[0], panel.lites[1]
        if a.nominal_key is None:
            a = LiteInput(nominal_key="6", glass=a.glass, construction=a.construction)
        if b.nominal_key is None:
            b = LiteInput(nominal_key="8", glass=b.glass, construction=b.construction)
        l1 = _to_spec(a)
        l2 = _to_spec(b)
        lr, det = governing_load_resistance_double_ig(s, ell, l1, l2, sup, duration=dur)
        ok = lr >= design_load_kpa
        return lr, ok, det, None

    # triple_ig
    lites = list(panel.lites)
    while len(lites) < 3:
        g0 = lites[0].glass if lites else "AN"
        lites.append(LiteInput(nominal_key="3", glass=g0))
    t1, t2, t3 = lites[0], lites[1], lites[2]
    for x in (t1, t2, t3):
        if x.nominal_key is None:
            x.nominal_key = "3"
    l1 = _to_spec(t1)
    l2 = _to_spec(t2)
    l3 = _to_spec(t3)
    lr, det = governing_load_resistance_triple_ig(s, ell, l1, l2, l3, sup, duration=dur)
    ok = lr >= design_load_kpa
    return lr, ok, det, None
