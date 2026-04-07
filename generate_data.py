"""Generate E1300_Research_Dataset.csv using the ASTM E1300-24 oracle (see docs/DATASET.md)."""

from __future__ import annotations

from e1300.dataset import export_csv

if __name__ == "__main__":
    path = export_csv(max_rows=8000, design_load_kpa=3.0)
    print(f"Wrote {path}")
