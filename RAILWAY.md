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

10. **Grasshopper / scripts**: use that **same base URL** (no trailing slash required for the API). Example:
    - `POST https://<your-domain>/api/analyze` with JSON per `app/schemas.py`.

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
| GET | `/` | HTML dashboard (`app/static/dashboard.html`) |
| POST | `/api/analyze` | JSON body per `app/schemas.py` |
| GET | `/api/last` | Last in-memory result (optional `?session_id=`) |
| GET | `/static/wind_terrain_reference.png` | Optional terrain diagram (see below) |

---

## Optional: terrain reference image on the dashboard

To show a textbook-style terrain diagram next to the wind chart, save your PNG as:

`app/static/wind_terrain_reference.png`

Commit and redeploy. The dashboard loads it automatically; if the file is missing, that panel stays hidden.

---

## Regenerate ML bundle (local or CI)

```bash
python scripts/train_ml.py
```

Commit `models/ml_bundle.npz` + `models/ml_meta.json` or bake them into the image after training in CI.

The deployed **ML** layer is a **k-nearest neighbors** predictor on NumPy arrays (no sklearn in the container). Training labels come from the same ASTM E1300 oracle used for the “oracle” column in the API response.
