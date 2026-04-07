"""Multi-algorithm ML prediction: k-NN (NumPy), Ridge, SVR, K-means (scikit-learn)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

_MODEL_DIR = Path(__file__).resolve().parents[1] / "models"

_bundle = None
_meta: dict | None = None
_registry: dict | None = None

_scaler = None
_ridge_reg = None
_ridge_cls = None
_svr_reg = None
_svc_cls = None
_kmeans = None
_sklearn_loaded = False


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


def load_sklearn_models() -> None:
    """Load scikit-learn models (Ridge, SVR, K-means) if available."""
    global _sklearn_loaded, _scaler, _ridge_reg, _ridge_cls, _svr_reg, _svc_cls, _kmeans
    if _sklearn_loaded:
        return
    _sklearn_loaded = True
    try:
        import joblib
    except ImportError:
        return

    def _load(name: str):
        p = _MODEL_DIR / name
        if p.is_file():
            return joblib.load(p)
        return None

    _scaler = _load("scaler.joblib")
    _ridge_reg = _load("ridge_reg.joblib")
    _ridge_cls = _load("ridge_cls.joblib")
    _svr_reg = _load("svr_reg.joblib")
    _svc_cls = _load("svc_cls.joblib")
    _kmeans = _load("kmeans.joblib")


def load_registry() -> dict:
    """Strategy list for all algorithms."""
    global _registry
    if _registry is not None:
        return _registry
    rp = _MODEL_DIR / "ml_registry.json"
    if rp.is_file():
        _registry = json.loads(rp.read_text(encoding="utf-8"))
    else:
        load_models()
        k = int((_meta or {}).get("knn_k", 7))
        _registry = {
            "default_strategy_id": "knn_default",
            "strategies": [
                {
                    "id": "knn_default",
                    "type": "knn",
                    "knn_k": k,
                    "label": f"k-NN (k={k})",
                }
            ],
        }
    return _registry


def _feature_importance() -> dict[str, float] | None:
    """Inverse-std heuristic for feature weights (teaching visualization)."""
    load_models()
    if _bundle is None or _meta is None:
        return None
    X_train = _bundle["X"]
    names = _meta.get(
        "feature_names",
        ["short_m", "long_m", "aspect_ratio", "design_load_kpa", "elevation_m", "z0_m", "v_at_panel_m_s"],
    )
    imp = {names[i]: 1.0 / (np.std(X_train[:, i]) + 1e-9) for i in range(len(names))}
    s = sum(imp.values())
    return {a: float(b / s) for a, b in imp.items()}


def _knn_indices(X_train: np.ndarray, x: np.ndarray, k: int) -> np.ndarray:
    d = np.sum((X_train - x) ** 2, axis=1)
    k = min(k, len(d))
    return np.argpartition(d, k - 1)[:k]


def predict_ml_row(
    features: list[float],
    knn_k: int | None = None,
) -> tuple[str | None, float | None, dict[str, float] | None]:
    """k-NN prediction (original interface, kept for backward compatibility)."""
    load_models()
    if _bundle is None or _meta is None:
        return None, None, None
    X_train = _bundle["X"]
    y_cls = _bundle["y_cls"]
    y_lr = _bundle["y_lr"]
    x = np.array(features, dtype=np.float64).reshape(1, -1)
    k = int(knn_k if knn_k is not None else _meta.get("knn_k", 7))
    idx = _knn_indices(X_train, x[0], k)
    vals, counts = np.unique(y_cls[idx], return_counts=True)
    cls = int(vals[np.argmax(counts)])
    nominal_keys = _meta.get("nominal_keys", [])
    nk = nominal_keys[cls] if cls < len(nominal_keys) else None
    lr_hat = float(np.mean(y_lr[idx]))
    imp = _feature_importance()
    return nk, lr_hat, imp


def predict_ridge(features: list[float]) -> tuple[str | None, float | None, dict[str, float] | None]:
    """Ridge regression prediction."""
    load_models()
    load_sklearn_models()
    if _ridge_reg is None or _ridge_cls is None or _meta is None:
        return None, None, None
    x = np.array(features, dtype=np.float64).reshape(1, -1)
    lr_hat = float(_ridge_reg.predict(x)[0])
    cls = int(_ridge_cls.predict(x)[0])
    nominal_keys = _meta.get("nominal_keys", [])
    nk = nominal_keys[cls] if 0 <= cls < len(nominal_keys) else None
    imp = _feature_importance()
    return nk, lr_hat, imp


def predict_svr(features: list[float]) -> tuple[str | None, float | None, dict[str, float] | None]:
    """SVR prediction (uses scaled features)."""
    load_models()
    load_sklearn_models()
    if _svr_reg is None or _svc_cls is None or _scaler is None or _meta is None:
        return None, None, None
    x = np.array(features, dtype=np.float64).reshape(1, -1)
    x_scaled = _scaler.transform(x)
    lr_hat = float(_svr_reg.predict(x_scaled)[0])
    cls = int(_svc_cls.predict(x_scaled)[0])
    nominal_keys = _meta.get("nominal_keys", [])
    nk = nominal_keys[cls] if 0 <= cls < len(nominal_keys) else None
    imp = _feature_importance()
    return nk, lr_hat, imp


def predict_kmeans(features: list[float]) -> tuple[int | None, float | None, dict[str, float] | None]:
    """K-means cluster assignment (unsupervised -- no nominal key or LR prediction)."""
    load_models()
    load_sklearn_models()
    if _kmeans is None or _scaler is None:
        return None, None, None
    x = np.array(features, dtype=np.float64).reshape(1, -1)
    x_scaled = _scaler.transform(x)
    cluster_id = int(_kmeans.predict(x_scaled)[0])
    imp = _feature_importance()
    return cluster_id, None, imp


def predict_by_algorithm(
    features: list[float],
    strategy: dict,
) -> tuple[str | None, float | None, dict[str, float] | None, str]:
    """
    Dispatch prediction to the right algorithm based on strategy dict.
    Returns (nominal_key_or_cluster, lr_estimate, feature_importance, backend_name).
    """
    algo_type = strategy.get("type", "knn")

    if algo_type == "knn":
        kk = int(strategy.get("knn_k", 7))
        nk, lr, imp = predict_ml_row(features, knn_k=kk)
        return nk, lr, imp, "numpy_knn"

    if algo_type == "ridge":
        nk, lr, imp = predict_ridge(features)
        return nk, lr, imp, "sklearn_ridge"

    if algo_type == "svr":
        nk, lr, imp = predict_svr(features)
        return nk, lr, imp, "sklearn_svr"

    if algo_type == "kmeans":
        cluster_id, _, imp = predict_kmeans(features)
        nk_str = f"cluster_{cluster_id}" if cluster_id is not None else None
        return nk_str, None, imp, "sklearn_kmeans"

    nk, lr, imp = predict_ml_row(features)
    return nk, lr, imp, "numpy_knn"
