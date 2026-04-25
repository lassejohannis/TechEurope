"""Auth layer for /api/* and /mcp/*.

Two principal sources:
  • Supabase JWT (HS256, SUPABASE_JWT_SECRET) — UI / human users.
  • agent_tokens table (bcrypt-hashed bearer) — programmatic / MCP clients.

`API_AUTH_DISABLED=true` (dev default) returns an anonymous admin principal,
so local development and existing tests don't break.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.config import settings

logger = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str           # user id, agent token id, or "anonymous"
    kind: str              # "user" | "agent" | "anonymous"
    scopes: tuple[str, ...]  # e.g. ("read","write","admin")

    def has_scope(self, *required: str) -> bool:
        return all(s in self.scopes for s in required)


ANON_PRINCIPAL = Principal(subject="anonymous", kind="anonymous", scopes=("read", "write", "admin"))


def _decode_jwt(token: str) -> Principal | None:
    """Decode a Supabase HS256 JWT. Returns None on failure."""
    if not settings.supabase_jwt_secret:
        return None
    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None
    sub = claims.get("sub") or claims.get("user_id") or "unknown"
    role = claims.get("role", "authenticated")
    # service_role JWTs get full scopes; everyone else read+write.
    scopes = ("read", "write", "admin") if role == "service_role" else ("read", "write")
    return Principal(subject=str(sub), kind="user", scopes=scopes)


def _verify_agent_token(token: str) -> Principal | None:
    """Look up an agent_tokens row by hash prefix and bcrypt-verify."""
    from server.auth.tokens import verify_agent_token

    row = verify_agent_token(token)
    if not row:
        return None
    scopes = tuple(row.get("scopes") or ["read"])
    return Principal(subject=str(row["id"]), kind="agent", scopes=scopes)


def get_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    """FastAPI dependency: extract principal from Authorization header.

    401 if a token is supplied but invalid. Anonymous bypass only when
    API_AUTH_DISABLED=true AND no header was sent.
    """
    if creds is None:
        if settings.api_auth_disabled:
            return ANON_PRINCIPAL
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials
    principal = _decode_jwt(token) or _verify_agent_token(token)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_scope(*required: str):
    """Dependency factory: principal must hold every named scope."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has_scope(*required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing scope(s): {', '.join(required)}",
            )
        return principal

    return _dep


__all__ = ["Principal", "get_principal", "require_scope", "ANON_PRINCIPAL"]
