"""Tests for FastAPI routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.config import settings


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "tech-europe-server"


def test_hello(client):
    resp = client.get("/api/hello")
    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.skipif(
    not settings.supabase_secret_key,
    reason="Requires live Supabase credentials",
)
def test_reload_ontologies(client):
    resp = client.post("/api/admin/reload-ontologies")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in ("ok", "stub")
    assert isinstance(body.get("loaded"), list)
    assert len(body["loaded"]) >= 4
