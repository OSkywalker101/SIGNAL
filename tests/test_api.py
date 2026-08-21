"""API smoke tests — DB-backed tests skip automatically when PostgreSQL is unreachable."""
import os
import pathlib

os.environ.setdefault("SIGNAL_PG_PORT", "5432")

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def db_up():
    try:
        from api import db
        db.fetch_one("SELECT 1 AS ok")
        return True
    except Exception:
        return False


def test_root_redirects_to_app():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307)
    assert "/app" in r.headers["location"]


def test_health_shape():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] == "ok"
    assert "db" in body and "n8n" in body


def test_investigate_requires_topic_or_url():
    r = client.post("/api/investigate", json={})
    assert r.status_code == 422


@pytest.mark.skipif(not db_up(), reason="postgres not reachable")
def test_stats_keys():
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_signals", "critical", "significant", "runs_24h", "channels"):
        assert key in body


@pytest.mark.skipif(not db_up(), reason="postgres not reachable")
def test_signals_list_and_detail():
    r = client.get("/api/signals?limit=5")
    assert r.status_code == 200
    rows = r.json()["signals"]
    assert isinstance(rows, list)
    if not rows:
        pytest.skip("no signals seeded")
    sid = rows[0]["signal_id"]
    d = client.get(f"/api/signals/{sid}")
    assert d.status_code == 200
    det = d.json()
    for section in ("signal", "sources", "claims", "hypotheses", "relationships",
                    "invalidators", "history"):
        assert section in det


@pytest.mark.skipif(not db_up(), reason="postgres not reachable")
def test_decision_validation():
    r = client.post("/api/signals/00000000-0000-0000-0000-000000000000/decision",
                    json={"decision": "NOT_A_DECISION"})
    assert r.status_code == 422
