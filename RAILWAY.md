# Railway deployment

This app is a **single Docker image** (FastAPI + static dashboard). No database. Railway injects `PORT`; the container listens on `0.0.0.0`.

---

## Step-by-step: connect Railway to this repo

Do these in order. You do **not** need to run the app on localhost first if you prefer to validate only on Railway.

1. **Push the repo to GitHub** (or GitLab, if Railway is connected to that). The repo root must contain the **`Dockerfile`** at the top level (this project already does).

2. **Open [Railway](https://railway.app)** and sign in. Open your **project** (or create one with **New project**).

3. **Add or select the service** that should run this API:
   - If you already added a service from this repo, click that service.
   - Otherwise: **New** → **GitHub Repo** → pick this repository → Railway creates a service.

4. **Point the service at the right branch** (usually `main`):
   - Service → **Settings** → **Source** → **Branch** → choose the branch you deploy from.

5. **Configure the build to use Docker** (this is the important part for “Build section”):
   - Service → **Settings** → **Build** (or **Deploy** → **Build** depending on UI version).
   - Set **Builder** to **Dockerfile** (not Nixpacks) if Railway offers a choice.
   - **Dockerfile path**: `Dockerfile` (repo root).
   - **Root directory**: `/` or leave empty (repo root). Only change this if the app lived in a subfolder.

6. **Leave the start command empty** in Railway if possible. This image already defines:
   - `CMD` → `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`  
   If Railway shows a custom start command, it should match that idea and **must** bind `0.0.0.0` and use `$PORT`.

7. **Deploy**: trigger a deploy (push to the connected branch, or **Deploy** → **Redeploy**). Watch the build logs until the image runs.

8. **Expose a public URL**:
   - Service → **Settings** → **Networking** → **Generate domain** (or **Public networking**).
   - Copy the HTTPS URL (for example `https://your-service.up.railway.app`).

9. **Smoke test in the browser**:
   - Open `https://<your-domain>/` — you should see the **E1300 teaching dashboard** (wind chart, roughness table, demo analyze).
   - Optional: `https://<your-domain>/docs` for OpenAPI.

10. **Grasshopper / scripts**: use that **same base URL** (no trailing slash). Paste-in templates live in the repo:
    - [`scripts/ghpython_send_panels.py`](scripts/ghpython_send_panels.py) — `POST /api/session` with panel geometry and `GH_Path` ids.
    - [`scripts/ghpython_receive_clusters.py`](scripts/ghpython_receive_clusters.py) — `GET /api/session/{session_id}/results` into cluster branches (ids + colors + thickness mm).
    - Example flow: upload session → `POST /api/session/{id}/calculate` (from the dashboard or API) → receive results in Grasshopper.

### Environment variables

- **`PORT`**: Railway sets this automatically. Do **not** override it unless you know you need to.
- No database or API keys are required for the current code.

### Health check (optional)

In Railway, you can set a health check path to **`/`** or **`/docs`** so the platform knows the service is up.

---

## What the Docker build does

- **Dockerfile** at repo root installs `requirements.txt` + `requirements-api.txt`, copies `e1300/`, `app/`, `building_code/e1300_data/`, `models/`.
- **Models**: `models/ml_bundle.npz` + `models/ml_meta.json` must be in the repo (or produced in CI before build) so inference works in the container.

---

## Service URLs (after deploy)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | HTML dashboard (`app/static/dashboard.html`), Tailwind + four panels (3D, wind, ML, clusters) |
| POST | `/api/session` | Upload `panels`; `session_id` optional (server creates UUID if omitted). Wind is **not** sent from GH — use **PUT** below or dashboard. |
| PUT | `/api/session/{id}/wind` | Set `v1_m_s`, `h1_m`, `z0_m`, `air_density_kg_m3`, `pressure_factor` from the **web app** (or API). |
| POST | `/api/session/{id}/calculate` | Run oracle + ML on stored panels using wind from the session (set in the web app). |
| GET | `/api/session/{id}/results` | Panels, clusters (colors + Table 4 min. mm), `input_geometry` for 3D when vertices were sent |
| POST | `/api/analyze` | Direct analyze: `panels` **or** `session_id` (loads panels from session) + `wind` |
| GET | `/api/last` | Last in-memory result (optional `?session_id=`) |
| GET | `/static/ardaena-logo.svg` | Ribbon logo |
| GET | `/static/wind_terrain_reference.png` | Optional terrain diagram (see below) |

---

## Optional: terrain reference image on the dashboard

To show a textbook-style terrain diagram next to the wind chart, save your PNG as:

`app/static/wind_terrain_reference.png`

Commit and redeploy. The dashboard loads it automatically; if the file is missing, that panel stays hidden.

---

## Regenerate ML bundle (local or CI)

Install dependencies from the repo root (same shell you use to run Python):

```bash
python -m pip install -r requirements.txt
# minimal training only (numpy + pydantic — enough for scripts/train_ml.py):
python -m pip install -r requirements-train.txt
python scripts/train_ml.py
```

If you see `ModuleNotFoundError` for `numpy` or `pydantic`, install into the **same** interpreter you use to run the script (Windows Store Python, conda base, etc.).

### “Application failed to respond” on Railway

1. **Health check** — This repo exposes **`GET /health`** (200 + JSON). The root **`railway.toml`** sets `healthcheckPath = "/health"`. In the Railway dashboard, under the service, set **Healthcheck path** to **`/health`** (or rely on the file after redeploy). If a healthcheck was set to a path that never returns 200, traffic may not switch to the new deployment.

2. **Public networking** — Service → **Settings** → **Networking** → generate a **public domain** (or confirm the URL targets **this** service).

3. **Port** — The container must listen on **`$PORT`** (Railway sets it, often `8080`). The Dockerfile uses `uvicorn ... --port ${PORT:-8000}`.

4. **Logs** — If deploy logs show `Uvicorn running on http://0.0.0.0:8080` but the site still fails, open **Deploy logs** for errors *after* startup, and try `curl -I https://<your-domain>/health` from your machine.

5. **Hostname allowlists** — If you add middleware that filters by `Host`, allow **`healthcheck.railway.app`** (Railway’s healthcheck hostname).

Commit `models/ml_bundle.npz` + `models/ml_meta.json` or bake them into the image after training in CI.

The deployed **ML** layer is a **k-nearest neighbors** predictor on NumPy arrays (no sklearn in the container). Training labels come from the same ASTM E1300 oracle used for the “oracle” column in the API response.

**Training host:** run `python scripts/train_ml.py` **locally or in CI**, then commit `models/` and redeploy. Railway runs **inference only**; training on the live web service is unnecessary for this workshop.

**Sessions:** panel data and results are stored **in memory** in the API process. A restart or new deploy clears all sessions.
