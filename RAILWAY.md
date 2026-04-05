# Railway deployment

## Build

- **Dockerfile** at repo root installs `requirements.txt` + `requirements-api.txt`, copies `e1300/`, `app/`, `building_code/e1300_data/`, `models/`.
- **Start command** (default in Dockerfile): `uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`  
  Railway injects `PORT`; do not hardcode 8000 in production.

## Service URLs

- `GET /` — HTML dashboard (`app/static/dashboard.html`).
- `POST /api/analyze` — JSON body per [`app/schemas.py`](app/schemas.py).
- `GET /api/last?session_id=` — last in-memory result (optional `session_id`; default bucket `default`).

## Environment

No database. In-memory store resets on deploy/restart.

## Health

Optional: add Railway healthcheck on `GET /` or `GET /docs` (OpenAPI).

## Regenerate ML bundle

```bash
python scripts/train_ml.py
```

Commit `models/ml_bundle.npz` + `models/ml_meta.json` or bake into the image after training in CI.

The deployed **ML** layer is a **k-nearest neighbors** predictor on NumPy arrays (no sklearn dependency in the container). Training labels come from the same ASTM E1300 oracle used for the “code” column in the API response.
