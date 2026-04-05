"""FastAPI teaching service: wind profile + ASTM E1300 oracle + KNN ML."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ml_predict import predict_ml_row
from app.oracle_panel import run_oracle_panel
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    LastResultStore,
    MLResult,
    OracleResult,
    PanelResult,
    WindDerived,
)
from app.wind import design_pressure_kpa

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from app.ml_predict import load_models

    load_models()
    yield


app = FastAPI(title="E1300 Teaching API", version="0.1.0", lifespan=_lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_LAST: dict[str, LastResultStore | None] = {"default": None}


def _features(panel, wind, design_kpa: float) -> list[float]:
    s = min(panel.width_m, panel.height_m)
    ell = max(panel.width_m, panel.height_m)
    ar = ell / s if s > 0 else 1.0
    v2, _q, _ = design_pressure_kpa(wind, panel.elevation_m)
    return [s, ell, ar, design_kpa, panel.elevation_m, wind.z0_m, v2]


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    out: list[PanelResult] = []
    for p in req.panels:
        v2, q_pa, design = design_pressure_kpa(req.wind, p.elevation_m)
        lr, ok, det, min_nk = run_oracle_panel(p, design)
        feats = _features(p, req.wind, design)
        pn, lr_ml, imp = predict_ml_row(feats)
        ml = MLResult(
            predicted_nominal_key=pn,
            predicted_governing_LR_kpa=lr_ml,
            ml_backend="numpy_knn" if lr_ml is not None else None,
            ml_available=lr_ml is not None,
            feature_importance=imp,
        )
        out.append(
            PanelResult(
                id=p.id,
                short_m=min(p.width_m, p.height_m),
                long_m=max(p.width_m, p.height_m),
                wind=WindDerived(
                    v_at_panel_m_s=v2,
                    dynamic_pressure_kpa=q_pa,
                    design_load_kpa=design,
                ),
                oracle=OracleResult(
                    governing_LR_kpa=lr,
                    acceptable=ok,
                    details=det,
                    minimum_nominal_key=min_nk,
                ),
                ml=ml,
            )
        )
    resp = AnalyzeResponse(
        panels=out,
        raw_request_echo=req.model_dump(),
    )
    key = req.session_id or "default"
    _LAST[key] = LastResultStore(
        request=req.model_dump(),
        response=resp.model_dump(),
    )
    return resp


@app.get("/api/last")
def api_last(session_id: str | None = None):
    key = session_id or "default"
    st = _LAST.get(key)
    if st is None:
        return JSONResponse({"ok": False, "message": "no request yet"}, status_code=404)
    return {"ok": True, **st.model_dump()}


@app.get("/dashboard")
def dashboard():
    html = STATIC / "dashboard.html"
    if not html.is_file():
        return JSONResponse({"error": "dashboard missing"}, status_code=500)
    return FileResponse(html)


@app.get("/")
def root():
    return FileResponse(STATIC / "dashboard.html")


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
