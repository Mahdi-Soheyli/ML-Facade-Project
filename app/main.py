"""FastAPI teaching service: wind profile + ASTM E1300 oracle + KNN ML."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.clustering import build_clusters
from app.ml_predict import predict_ml_row
from app.oracle_panel import run_oracle_panel
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ClusterGroup,
    LastResultStore,
    MLResult,
    OracleResult,
    PanelInput,
    PanelResult,
    SessionCalculateRequest,
    SessionResultsResponse,
    SessionUploadRequest,
    SessionUploadResponse,
    WindDerived,
    WindParams,
)
from app.wind import design_pressure_kpa

STATIC = Path(__file__).resolve().parent / "static"


@dataclass
class SessionState:
    wind: WindParams
    panels: list[PanelInput]
    analyze_response: AnalyzeResponse | None = None
    clusters: list[ClusterGroup] = field(default_factory=list)


SESSIONS: dict[str, SessionState] = {}

_LAST: dict[str, LastResultStore | None] = {"default": None}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from app.ml_predict import load_models

    load_models()
    yield


app = FastAPI(title="E1300 Teaching API", version="0.2.0", lifespan=_lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _features(panel: PanelInput, wind: WindParams, design_kpa: float) -> list[float]:
    assert panel.width_m is not None and panel.height_m is not None
    s = min(panel.width_m, panel.height_m)
    ell = max(panel.width_m, panel.height_m)
    ar = ell / s if s > 0 else 1.0
    v2, _q, _ = design_pressure_kpa(wind, panel.elevation_m)
    return [s, ell, ar, design_kpa, panel.elevation_m, wind.z0_m, v2]


def _run_analyze(wind: WindParams, panels: list[PanelInput]) -> AnalyzeResponse:
    out: list[PanelResult] = []
    for p in panels:
        p = p.as_sized()
        v2, q_pa, design = design_pressure_kpa(wind, p.elevation_m)
        lr, ok, det, min_nk = run_oracle_panel(p, design)
        feats = _features(p, wind, design)
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
    raw_echo: dict[str, Any] = {
        "wind": wind.model_dump(),
        "panels": [x.model_dump() for x in panels],
    }
    return AnalyzeResponse(panels=out, raw_request_echo=raw_echo)


def _resolve_session_wind(session_id: str, body_wind: WindParams | None) -> WindParams:
    """Wind from request body, else keep existing session wind, else API default."""
    if body_wind is not None:
        return body_wind
    st = SESSIONS.get(session_id)
    if st is not None:
        return st.wind
    return WindParams()


@app.put("/api/session/{session_id}/wind")
def session_put_wind(session_id: str, wind: WindParams) -> dict[str, Any]:
    """Create or update session wind only (panels unchanged if session exists)."""
    sid = session_id.strip()
    if not sid:
        raise HTTPException(status_code=422, detail="invalid session_id")
    if sid in SESSIONS:
        SESSIONS[sid].wind = wind
    else:
        SESSIONS[sid] = SessionState(wind=wind, panels=[])
    return {"ok": True, "session_id": sid, "wind": wind.model_dump()}


@app.post("/api/session", response_model=SessionUploadResponse)
def session_upload(body: SessionUploadRequest) -> SessionUploadResponse:
    sid = (body.session_id or "").strip() or str(uuid.uuid4())
    wind = _resolve_session_wind(sid, body.wind)
    preview: list[dict[str, Any]] = []
    resolved: list[PanelInput] = []
    for p in body.panels:
        p = p.as_sized()
        resolved.append(p)
        preview.append(
            {
                "id": p.id,
                "width_m": p.width_m,
                "height_m": p.height_m,
                "resolved_from_geometry": p.resolved_from_geometry,
                "n_edges": p.n_edges,
            }
        )
    SESSIONS[sid] = SessionState(wind=wind, panels=resolved)
    return SessionUploadResponse(
        session_id=sid,
        panel_count=len(resolved),
        resolved_preview=preview,
    )


@app.post("/api/session/{session_id}/calculate", response_model=AnalyzeResponse)
def session_calculate(
    session_id: str,
    body: SessionCalculateRequest = Body(default_factory=SessionCalculateRequest),
) -> AnalyzeResponse:
    st = SESSIONS.get(session_id)
    if st is None:
        raise HTTPException(status_code=404, detail="session not found")
    # Wind always comes from session (set in the web app via PUT .../wind).
    w = st.wind
    resp = _run_analyze(w, st.panels)
    st.analyze_response = resp
    pr_list = [p.model_dump() for p in resp.panels]
    st.clusters = build_clusters(pr_list)
    key = session_id
    _LAST[key] = LastResultStore(
        request={"session_id": session_id, "wind": w.model_dump()},
        response=resp.model_dump(),
    )
    return resp


@app.get("/api/session/{session_id}/results", response_model=SessionResultsResponse)
def session_results(session_id: str) -> SessionResultsResponse:
    st = SESSIONS.get(session_id)
    if st is None:
        raise HTTPException(status_code=404, detail="session not found")
    if st.analyze_response is None:
        raise HTTPException(status_code=400, detail="run POST /api/session/{id}/calculate first")
    ar = st.analyze_response
    panel_rows: list[dict[str, Any]] = []
    for idx, p in enumerate(ar.panels):
        d = p.model_dump()
        oid = d["id"]
        cl_idx = None
        color = None
        for c in st.clusters:
            if oid in c.panel_ids:
                cl_idx = c.cluster_index
                color = c.color_hex
                break
        d["cluster_index"] = cl_idx
        d["cluster_color_hex"] = color
        pin = st.panels[idx] if idx < len(st.panels) else None
        if pin is not None and pin.vertices_m and pin.n_edges:
            d["input_geometry"] = {
                "n_edges": pin.n_edges,
                "vertices_m": pin.vertices_m,
                "normal": pin.normal,
            }
        panel_rows.append(d)
    return SessionResultsResponse(
        session_id=session_id,
        wind=st.wind.model_dump(),
        panels=panel_rows,
        clusters=st.clusters,
        analyze=ar.model_dump(),
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    panels_in: list[PanelInput] | None = req.panels
    if not panels_in and req.session_id:
        st = SESSIONS.get(req.session_id)
        if st is None:
            raise HTTPException(status_code=404, detail="session not found")
        panels_in = st.panels
        wind = req.wind
    else:
        wind = req.wind
    if not panels_in:
        raise HTTPException(status_code=422, detail="Provide panels or a valid session_id with uploaded panels")

    resp = _run_analyze(wind, panels_in)
    resp = AnalyzeResponse(
        panels=resp.panels,
        raw_request_echo={
            **(resp.raw_request_echo or {}),
            "session_id": req.session_id,
        },
    )
    key = req.session_id or "default"
    _LAST[key] = LastResultStore(
        request=req.model_dump(),
        response=resp.model_dump(),
    )
    if req.session_id and req.session_id in SESSIONS:
        st = SESSIONS[req.session_id]
        st.wind = wind
        st.analyze_response = resp
        pr_list = [p.model_dump() for p in resp.panels]
        st.clusters = build_clusters(pr_list)
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
