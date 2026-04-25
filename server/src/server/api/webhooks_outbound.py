"""Outbound webhooks — admin CRUD."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from server.auth import Principal, require_scope
from server.db import get_db

router = APIRouter(prefix="/admin/webhooks", tags=["admin", "webhooks"])

ALLOWED_EVENTS = {"fact.created", "fact.superseded", "entity.created", "entity.merged"}


class WebhookCreateRequest(BaseModel):
    url: HttpUrl
    event_types: list[str] = Field(..., min_length=1)


class WebhookResponse(BaseModel):
    id: str
    url: str
    event_types: list[str]
    secret: str | None = None
    active: bool
    created_at: str | None = None


@router.post("", response_model=WebhookResponse, status_code=201)
def create_webhook(
    req: WebhookCreateRequest,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
):
    bad = set(req.event_types) - ALLOWED_EVENTS
    if bad:
        raise HTTPException(status_code=400, detail=f"Unsupported event_types: {sorted(bad)}")

    wh_id = uuid.uuid4().hex[:16]
    secret = secrets.token_urlsafe(32)
    row = {
        "id": wh_id,
        "url": str(req.url),
        "secret": secret,
        "event_types": req.event_types,
        "created_by": principal.subject,
        "active": True,
    }
    db.table("webhooks").insert(row).execute()
    # Return secret ONCE so the operator can save it.
    return WebhookResponse(
        id=wh_id, url=str(req.url), event_types=req.event_types,
        secret=secret, active=True,
    )


@router.get("", response_model=list[WebhookResponse])
def list_webhooks(
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
):
    res = db.table("webhooks").select(
        "id, url, event_types, active, created_at"
    ).order("created_at", desc=True).execute()
    return [WebhookResponse(**r) for r in (res.data or [])]


@router.delete("/{webhook_id}", status_code=200)
def delete_webhook(
    webhook_id: str,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
) -> dict[str, Any]:
    res = db.table("webhooks").delete().eq("id", webhook_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": webhook_id}
