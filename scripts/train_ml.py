"""
Train KNN memory bank + LR targets from oracle labels (NumPy only — no sklearn).

Run from repo root:
  python scripts/train_ml.py

Install deps (pick one):
  python -m pip install -r requirements-train.txt
  # or full project deps (matches Docker / Railway, pins numpy<2):
  python -m pip install -r requirements.txt

Use the **same** `python` for `pip install` and for `python scripts/train_ml.py` (e.g. VS Code’s
interpreter, conda, or Windows Store Python). If you see `ModuleNotFoundError` for numpy or
pydantic, install requirements-train into that interpreter.

Outputs: models/ml_bundle.npz, models/ml_meta.json
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.oracle_panel import minimum_nominal_single  # noqa: E402
from app.wind import design_pressure_kpa, wind_speed_at_height  # noqa: E402
from app.schemas import WindParams  # noqa: E402


def main() -> None:
    random.seed(42)
    np.random.seed(42)
    nominal_path = ROOT / "building_code" / "e1300_data" / "tables.json"
    nominal_keys = json.loads(nominal_path.read_text(encoding="utf-8"))["nominal_keys_ordered"]
    key_to_idx = {k: i for i, k in enumerate(nominal_keys)}

    rows: list[list[float]] = []
    y_cls: list[int] = []
    y_lr: list[float] = []

    z0_opts = [0.0002, 0.03, 0.1, 0.4, 0.6, 1.6]

    for _ in range(4000):
        short = random.uniform(0.5, 3.0)
        long = random.uniform(short, 4.0)
        z0 = random.choice(z0_opts)
        v1 = random.uniform(4.0, 20.0)
        h1 = 10.0
        elev = random.uniform(10.0, 150.0)
        v2 = wind_speed_at_height(v1, h1, max(elev, z0 + 0.01), z0)
        wp = WindParams(
            v1_m_s=v1,
            h1_m=h1,
            z0_m=z0,
            pressure_factor=1.0,
        )
        _, _, design = design_pressure_kpa(wp, elev)

        nk, lr, _ok, _det = minimum_nominal_single(
            short,
            long,
            "AN",
            "monolithic",
            "monolithic_four_sides",
            design,
            "short",
        )
        ar = long / short if short > 0 else 1.0
        rows.append([short, long, ar, design, elev, z0, v2])
        y_cls.append(key_to_idx[nk])
        y_lr.append(lr)

    X = np.array(rows, dtype=np.float64)
    yc = np.array(y_cls, dtype=np.int32)
    yr = np.array(y_lr, dtype=np.float64)

    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    np.savez_compressed(
        out / "ml_bundle.npz",
        X=X,
        y_cls=yc,
        y_lr=yr,
    )
    meta = {
        "nominal_keys": nominal_keys,
        "feature_names": [
            "short_m",
            "long_m",
            "aspect_ratio",
            "design_load_kpa",
            "elevation_m",
            "z0_m",
            "v_at_panel_m_s",
        ],
        "knn_k": 7,
        "backend": "numpy_knn",
    }
    (out / "ml_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("Wrote", out / "ml_bundle.npz")


if __name__ == "__main__":
    main()
