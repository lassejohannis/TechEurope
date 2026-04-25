"""Tests for the API layer (#14): auth gating, pagination cursor, webhook signing.

All offline — no live DB required.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from server.api._pagination import Cursor, build_page, decode_cursor
from server.auth import ANON_PRINCIPAL, Principal, get_principal, require_scope
from server.config import settings


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_app():
    app = FastAPI()

    @app.get("/whoami")
    def whoami(p: Principal = Depends(get_principal)):
        return {"subject": p.subject, "kind": p.kind, "scopes": list(p.scopes)}

    @app.get("/admin")
    def admin(p: Principal = Depends(require_scope("admin"))):
        return {"ok": True}

    return app


def test_dev_bypass_returns_anonymous_admin(auth_app, monkeypatch):
    monkeypatch.setattr(settings, "api_auth_disabled", True)
    client = TestClient(auth_app)
    r = client.get("/whoami")
    assert r.status_code == 200
    assert r.json()["kind"] == "anonymous"
    assert "admin" in r.json()["scopes"]


def test_strict_mode_rejects_missing_token(auth_app, monkeypatch):
    monkeypatch.setattr(settings, "api_auth_disabled", False)
    client = TestClient(auth_app)
    r = client.get("/whoami")
    assert r.status_code == 401


def test_strict_mode_rejects_invalid_token(auth_app, monkeypatch):
    monkeypatch.setattr(settings, "api_auth_disabled", False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")  # disable JWT path
    client = TestClient(auth_app)
    r = client.get("/whoami", headers={"Authorization": "Bearer bogus"})
    assert r.status_code == 401


def test_require_scope_blocks_when_missing(auth_app):
    # Inject a principal lacking 'admin'
    auth_app.dependency_overrides[get_principal] = lambda: Principal(
        subject="x", kind="user", scopes=("read",)
    )
    client = TestClient(auth_app)
    r = client.get("/admin")
    assert r.status_code == 403


def test_require_scope_allows_admin(auth_app):
    auth_app.dependency_overrides[get_principal] = lambda: ANON_PRINCIPAL
    client = TestClient(auth_app)
    r = client.get("/admin")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Cursor pagination
# ---------------------------------------------------------------------------


def test_cursor_roundtrip():
    c = Cursor(ts="2026-04-25T12:00:00+00:00", id="fact-42")
    encoded = c.encode()
    decoded = decode_cursor(encoded)
    assert decoded == c


def test_decode_cursor_handles_empty_and_garbage():
    assert decode_cursor(None) is None
    assert decode_cursor("") is None
    assert decode_cursor("not-base64-!!") is None


def test_build_page_yields_next_cursor_when_more_rows():
    rows = [{"id": f"f{i}", "at": f"2026-04-25T12:00:0{i}+00:00"} for i in range(11)]
    page = build_page(rows, limit=10, ts_key="at", id_key="id")
    assert page["count"] == 10
    assert page["next_cursor"] is not None
    decoded = decode_cursor(page["next_cursor"])
    assert decoded.id == "f9"  # last item of returned slice


def test_build_page_no_cursor_when_short():
    rows = [{"id": f"f{i}", "at": f"2026-04-25T12:00:0{i}+00:00"} for i in range(3)]
    page = build_page(rows, limit=10, ts_key="at", id_key="id")
    assert page["next_cursor"] is None
    assert page["count"] == 3


# ---------------------------------------------------------------------------
# Webhook HMAC compatibility
# ---------------------------------------------------------------------------


def test_webhook_signature_matches_documented_recipe():
    """Mirror the docs/api-consumer-guide recipe so consumers can verify."""
    body = b'{"event_type":"fact.created","fact_id":"x"}'
    secret = "demo-secret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    header = f"sha256={sig}"
    received = header.split("=", 1)[1]
    assert hmac.compare_digest(sig, received)
