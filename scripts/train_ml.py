"""
Train all ML models from oracle labels: k-NN (NumPy), Ridge, SVR, K-means (scikit-learn).

Run from repo root:
  python scripts/train_ml.py

Install deps (pick one):
  python -m pip install -r requirements-train.txt
  # or full project deps (matches Docker / Railway, pins numpy<2):
  python -m pip install -r requirements.txt

Outputs:
  models/ml_bundle.npz      -- training matrix + labels (shared by k-NN strategies)
  models/ml_meta.json        -- feature names, nominal key order, legacy default knn_k
  models/ml_registry.json    -- all algorithm strategies for the API and charts
  models/scaler.joblib       -- StandardScaler fitted on training features
  models/ridge_reg.joblib    -- Ridge regression for LR prediction
  models/ridge_cls.joblib    -- RidgeClassifier for nominal class
  models/svr_reg.joblib      -- SVR for LR prediction
  models/svc_cls.joblib      -- SVC for nominal classification
  models/kmeans.joblib       -- KMeans clustering on feature space
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import joblib

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

    # k-NN bundle (NumPy, unchanged)
    np.savez_compressed(out / "ml_bundle.npz", X=X, y_cls=yc, y_lr=yr)
    print("Wrote", out / "ml_bundle.npz")

    # StandardScaler (needed for SVR, K-means)
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, out / "scaler.joblib")
    print("Wrote", out / "scaler.joblib")

    # Ridge Regression (LR) + RidgeClassifier (nominal)
    from sklearn.linear_model import Ridge, RidgeClassifier

    ridge_reg = Ridge(alpha=1.0)
    ridge_reg.fit(X, yr)
    joblib.dump(ridge_reg, out / "ridge_reg.joblib")
    print("Wrote", out / "ridge_reg.joblib")

    ridge_cls = RidgeClassifier(alpha=1.0)
    ridge_cls.fit(X, yc)
    joblib.dump(ridge_cls, out / "ridge_cls.joblib")
    print("Wrote", out / "ridge_cls.joblib")

    # SVR (LR) + SVC (nominal) -- trained on scaled features
    from sklearn.svm import SVR, SVC

    svr_reg = SVR(kernel="rbf", C=10.0, epsilon=0.05)
    svr_reg.fit(X_scaled, yr)
    joblib.dump(svr_reg, out / "svr_reg.joblib")
    print("Wrote", out / "svr_reg.joblib")

    svc_cls = SVC(kernel="rbf", C=10.0)
    svc_cls.fit(X_scaled, yc)
    joblib.dump(svc_cls, out / "svc_cls.joblib")
    print("Wrote", out / "svc_cls.joblib")

    # K-means clustering on scaled feature space
    from sklearn.cluster import KMeans

    n_clusters = min(6, len(nominal_keys))
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    kmeans.fit(X_scaled)
    joblib.dump(kmeans, out / "kmeans.joblib")
    print("Wrote", out / "kmeans.joblib")

    # Metadata
    feature_names = [
        "short_m",
        "long_m",
        "aspect_ratio",
        "design_load_kpa",
        "elevation_m",
        "z0_m",
        "v_at_panel_m_s",
    ]
    meta = {
        "nominal_keys": nominal_keys,
        "feature_names": feature_names,
        "knn_k": 7,
        "backend": "multi_algorithm",
        "kmeans_n_clusters": n_clusters,
    }
    (out / "ml_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("Wrote", out / "ml_meta.json")

    # Registry: all algorithms
    registry = {
        "default_strategy_id": "knn_k7",
        "strategies": [
            {"id": "knn_k3", "type": "knn", "knn_k": 3, "label": "k-NN (k=3)"},
            {"id": "knn_k7", "type": "knn", "knn_k": 7, "label": "k-NN (k=7)"},
            {"id": "knn_k15", "type": "knn", "knn_k": 15, "label": "k-NN (k=15)"},
            {"id": "ridge", "type": "ridge", "label": "Ridge Regression"},
            {"id": "svr", "type": "svr", "label": "Support Vector Regression (SVR)"},
            {"id": "kmeans", "type": "kmeans", "label": "K-Means Clustering"},
        ],
    }
    (out / "ml_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print("Wrote", out / "ml_registry.json")


if __name__ == "__main__":
    main()
