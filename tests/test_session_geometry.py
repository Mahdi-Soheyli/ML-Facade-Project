"""Session + mixed geometry panels (tri + explicit rect)."""

from fastapi.testclient import TestClient

from app.main import app


def test_session_upload_tri_quad_and_calculate():
    c = TestClient(app)
    r = c.post(
        "/api/session",
        json={
            "session_id": "geom-mix",
            "wind": {"v1_m_s": 12.0, "h1_m": 10.0, "z0_m": 0.4},
            "panels": [
                {
                    "id": "0;0",
                    "n_edges": 3,
                    "vertices_m": [[0, 0, 0], [1.5, 0, 0], [0.75, 1.2, 0]],
                    "elevation_m": 25.0,
                    "case": "single_monolithic",
                    "support_family": "monolithic_four_sides",
                    "duration": "short",
                    "lites": [{"glass": "AN", "construction": "monolithic"}],
                },
                {
                    "id": "0;1",
                    "width_m": 1.0,
                    "height_m": 1.4,
                    "elevation_m": 30.0,
                    "case": "single_monolithic",
                    "support_family": "monolithic_four_sides",
                    "duration": "short",
                    "lites": [{"glass": "AN", "construction": "monolithic"}],
                },
            ],
        },
    )
    assert r.status_code == 200
    prev = r.json()["resolved_preview"]
    assert prev[0]["resolved_from_geometry"] is True
    assert prev[1]["resolved_from_geometry"] is False

    r2 = c.post("/api/session/geom-mix/calculate", json={})
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["panels"]) == 2

    r3 = c.get("/api/session/geom-mix/results")
    assert r3.status_code == 200
    out = r3.json()
    assert out["session_id"] == "geom-mix"
    assert len(out["panels"]) == 2
    assert "clusters" in out
    assert len(out["clusters"]) >= 1
    g0 = out["panels"][0].get("input_geometry")
    assert g0 is not None
    assert g0["n_edges"] == 3


def test_session_upload_without_session_id_gets_uuid():
    c = TestClient(app)
    r = c.post(
        "/api/session",
        json={
            "panels": [
                {
                    "id": "only",
                    "width_m": 1.0,
                    "height_m": 1.0,
                    "elevation_m": 10.0,
                    "case": "single_monolithic",
                    "support_family": "monolithic_four_sides",
                    "duration": "short",
                    "lites": [{"glass": "AN", "construction": "monolithic"}],
                }
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["session_id"]) >= 8
    assert data["panel_count"] == 1


def test_put_wind_creates_session():
    c = TestClient(app)
    r = c.put(
        "/api/session/wind-test-put/wind",
        json={"v1_m_s": 12.0, "h1_m": 10.0, "z0_m": 0.1, "pressure_factor": 1.0},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_analyze_by_session_id():
    c = TestClient(app)
    c.post(
        "/api/session",
        json={
            "session_id": "sess-a",
            "wind": {"v1_m_s": 10.0, "h1_m": 10.0, "z0_m": 0.4},
            "panels": [
                {
                    "id": "p1",
                    "width_m": 1.0,
                    "height_m": 1.0,
                    "elevation_m": 15.0,
                    "case": "single_monolithic",
                    "support_family": "monolithic_four_sides",
                    "duration": "short",
                    "lites": [{"glass": "AN", "construction": "monolithic"}],
                }
            ],
        },
    )
    r = c.post(
        "/api/analyze",
        json={
            "session_id": "sess-a",
            "wind": {"v1_m_s": 11.0, "h1_m": 10.0, "z0_m": 0.4},
        },
    )
    assert r.status_code == 200
    assert len(r.json()["panels"]) == 1
