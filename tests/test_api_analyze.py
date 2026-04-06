from fastapi.testclient import TestClient

from app.main import app


def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_single_panel():
    c = TestClient(app)
    r = c.post(
        "/api/analyze",
        json={
            "wind": {"v1_m_s": 5.0, "h1_m": 10, "z0_m": 0.4},
            "panels": [
                {
                    "id": "A",
                    "width_m": 1.2,
                    "height_m": 1.5,
                    "elevation_m": 20,
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
    assert len(data["panels"]) == 1
    assert "oracle" in data["panels"][0]
    assert "ml" in data["panels"][0]


def test_api_last():
    c = TestClient(app)
    c.post(
        "/api/analyze",
        json={
            "wind": {"v1_m_s": 5.0, "h1_m": 10, "z0_m": 0.4},
            "panels": [
                {
                    "id": "B",
                    "width_m": 1.0,
                    "height_m": 1.0,
                    "elevation_m": 15,
                    "case": "single_monolithic",
                    "support_family": "monolithic_four_sides",
                    "duration": "short",
                    "lites": [{"glass": "AN", "construction": "monolithic"}],
                }
            ],
        },
    )
    u = c.get("/api/last")
    assert u.status_code == 200
    assert u.json()["ok"] is True
