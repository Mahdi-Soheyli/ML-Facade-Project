"""Annex A3 worked examples — tolerances for NFL surrogate (charts are authoritative)."""

from __future__ import annotations

from e1300.lr import LiteSpec, governing_load_resistance_double_ig, governing_load_resistance_triple_ig
from e1300.nfl import nfl_kpa


def test_example_1_nfl_si():
    # A3.1 — 1200 mm x 1500 mm, 6 mm AN, NFL = 2.5 kPa
    n = nfl_kpa(1.2, 1.5, "6", construction="monolithic", support_family="monolithic_four_sides")
    assert abs(n - 2.5) < 0.02


def test_example_3_short_lr_asym_ig():
    # A3.3 — governing short LR = 6.75 kPa (6 mm FT + 8 mm HS LG)
    l1 = LiteSpec("6", "FT", "monolithic")
    l2 = LiteSpec("8", "HS", "laminated")
    g, _ = governing_load_resistance_double_ig(
        1.52, 1.9, l1, l2, "monolithic_four_sides", duration="short"
    )
    assert abs(g - 6.75) < 0.05


def test_example_6_triple_ig():
    # A3.6 — triple AN, governing short LR = 2.61 kPa
    a = LiteSpec("3", "AN", "monolithic")
    b = LiteSpec("2.5", "AN", "monolithic")
    g, _ = governing_load_resistance_triple_ig(
        1.0, 1.5, a, b, a, "monolithic_four_sides", duration="short"
    )
    assert abs(g - 2.61) < 0.05
