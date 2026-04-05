"""Load sklearn joblib models for GBDT + MLP (optional)."""

from __future__ import annotations

import json
from pathlib import Path

_MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


def _load_joblib(name: str):
    try:
        import joblib
    except ImportError:
        return None
    path = _MODEL_DIR / name
    if not path.is_file():
        return None
    return joblib.load(path)


_gbdt = None
_mlp = None
_meta: dict | None = None


def load_models() -> None:
    global _gbdt, _mlp, _meta
    _gbdt = _load_joblib("gbdt_nominal.joblib")
    _mlp = _load_joblib("mlp_lr.joblib")
    meta_path = _MODEL_DIR / "ml_meta.json"
    if meta_path.is_file():
        _meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        _meta = None


def predict_ml_row(features: list[float]) -> tuple[str | None, float | None, dict[str, float] | None]:
    """
    features order must match training script:
    short_m, long_m, aspect_ratio, design_load_kpa, elevation_m, z0_m, v_at_panel_m_s
    """
    load_models()
    nk = None
    lr = None
    imp: dict[str, float] | None = None
    if _gbdt is not None:
        import numpy as np

        x = np.array(features, dtype=float).reshape(1, -1)
        idx = int(_gbdt.predict(x)[0])
        if _meta and "nominal_keys" in _meta:
            nk = _meta["nominal_keys"][idx]
        if hasattr(_gbdt, "feature_importances_"):
            names = (_meta or {}).get(
                "feature_names",
                [
                    "short_m",
                    "long_m",
                    "aspect_ratio",
                    "design_load_kpa",
                    "elevation_m",
                    "z0_m",
                    "v_at_panel_m_s",
                ],
            )
            imp = {
                names[i]: float(_gbdt.feature_importances_[i])
                for i in range(len(names))
            }
    if _mlp is not None:
        import numpy as np

        x = np.array(features, dtype=float).reshape(1, -1)
        lr = float(_mlp.predict(x)[0])
    return nk, lr, imp
