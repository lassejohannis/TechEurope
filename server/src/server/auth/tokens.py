"""agent_tokens — bcrypt-hashed bearer tokens for programmatic API consumers.

Token format on the wire: `qx_<id>_<secret>` where:
  • `qx_` prefix lets us detect agent tokens vs Supabase JWTs at a glance.
  • `<id>` (12 hex chars) maps to agent_tokens.id — used for O(1) lookup.
  • `<secret>` (32 hex chars) is bcrypt-verified against agent_tokens.token_hash.

This avoids scanning every row on each request (the bcrypt cost only runs once).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

import bcrypt

from server.db import get_supabase

logger = logging.getLogger(__name__)


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def _verify(secret: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(secret.encode(), hashed.encode())
    except ValueError:
        return False


def issue_token(name: str, scopes: list[str]) -> tuple[str, str]:
    """Create a new agent_tokens row. Returns (token_id, full_token).

    The full_token is shown to the operator ONCE — only the bcrypt hash is stored.
    """
    token_id = secrets.token_hex(6)            # 12 hex chars
    secret = secrets.token_hex(16)             # 32 hex chars
    full_token = f"qx_{token_id}_{secret}"
    token_hash = _hash(secret)

    db = get_supabase()
    db.table("agent_tokens").insert({
        "id": token_id,
        "name": name,
        "token_hash": token_hash,
        "scopes": scopes,
    }).execute()
    return token_id, full_token


def revoke_token(token_id: str) -> bool:
    db = get_supabase()
    res = db.table("agent_tokens").update({
        "revoked_at": datetime.now(tz=timezone.utc).isoformat(),
    }).eq("id", token_id).execute()
    return bool(res.data)


def list_tokens() -> list[dict[str, Any]]:
    db = get_supabase()
    res = db.table("agent_tokens").select(
        "id, name, scopes, created_at, last_seen_at, revoked_at"
    ).order("created_at", desc=True).execute()
    return res.data or []


def verify_agent_token(raw: str) -> dict[str, Any] | None:
    """Validate `qx_<id>_<secret>`. Returns the agent_tokens row or None."""
    if not raw.startswith("qx_"):
        return None
    parts = raw.split("_", 2)
    if len(parts) != 3:
        return None
    _, token_id, secret = parts

    db = get_supabase()
    res = db.table("agent_tokens").select("*").eq("id", token_id).single().execute()
    row = res.data
    if not row or row.get("revoked_at"):
        return None
    if not _verify(secret, row["token_hash"]):
        return None

    # Touch last_seen_at (best-effort, don't block on failure).
    try:
        db.table("agent_tokens").update({
            "last_seen_at": datetime.now(tz=timezone.utc).isoformat()
        }).eq("id", token_id).execute()
    except Exception as exc:  # pragma: no cover
        logger.debug("agent_tokens.last_seen_at update failed: %s", exc)
    return row
