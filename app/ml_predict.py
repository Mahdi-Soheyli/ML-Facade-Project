"""KNN + numpy bundle (no sklearn) for Railway compatibility."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

_MODEL_DIR = Path(__file__).resolve().parents[1] / "models"

_bundle = None
_meta: dict | None = None


def load_models() -> None:
    global _bundle, _meta
    if _bundle is not None:
        return
    bp = _MODEL_DIR / "ml_bundle.npz"
    mp = _MODEL_DIR / "ml_meta.json"
    if not bp.is_file():
        _bundle = None
        _meta = None
        return
    _bundle = np.load(bp)
    _meta = json.loads(mp.read_text(encoding="utf-8")) if mp.is_file() else {}


def _knn_indices(X_train: np.ndarray, x: np.ndarray, k: int) -> np.ndarray:
    d = np.sum((X_train - x) ** 2, axis=1)
    k = min(k, len(d))
    return np.argpartition(d, k - 1)[:k]


def predict_ml_row(features: list[float]) -> tuple[str | None, float | None, dict[str, float] | None]:
    """
    features order:
    short_m, long_m, aspect_ratio, design_load_kpa, elevation_m, z0_m, v_at_panel_m_s
    """
    load_models()
    if _bundle is None or _meta is None:
        return None, None, None
    X_train = _bundle["X"]
    y_cls = _bundle["y_cls"]
    y_lr = _bundle["y_lr"]
    x = np.array(features, dtype=np.float64).reshape(1, -1)
    k = int(_meta.get("knn_k", 7))
    idx = _knn_indices(X_train, x[0], k)
    # classification: mode of neighbor classes
    vals, counts = np.unique(y_cls[idx], return_counts=True)
    cls = int(vals[np.argmax(counts)])
    nominal_keys = _meta.get("nominal_keys", [])
    nk = nominal_keys[cls] if cls < len(nominal_keys) else None
    lr_hat = float(np.mean(y_lr[idx]))
    names = _meta.get(
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
    # pseudo-importance: inverse variance contribution (teaching visualization only)
    imp = {names[i]: 1.0 / (np.std(X_train[:, i]) + 1e-9) for i in range(len(names))}
    s = sum(imp.values())
    imp = {a: float(b / s) for a, b in imp.items()}
    return nk, lr_hat, imp
