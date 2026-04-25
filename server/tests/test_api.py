"""Tests for FastAPI routes (no Supabase required)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


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


def test_reload_ontologies_dry_run(client):
    """Without supabase creds the endpoint returns dry-run mode."""
    resp = client.post("/admin/reload-ontologies")
    assert resp.status_code == 200
    body = resp.json()
    assert "loaded" in body
    assert "mode" in body
    assert body["mode"] in ("dry-run", "applied")
    assert isinstance(body["loaded"], list)
    assert len(body["loaded"]) >= 4


def test_reload_ontologies_alias(client):
    resp = client.post("/api/admin/reload-ontologies")
    assert resp.status_code == 200
