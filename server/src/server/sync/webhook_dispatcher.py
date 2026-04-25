"""Outbound webhook dispatcher.

LISTENs on the Postgres `qontext_events` channel (see migration 009), filters
each event against active webhook subscriptions, and POSTs HMAC-signed JSON
with retry. Pattern mirrors `sync.neo4j_projection` — long-lived asyncio task
managed by the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from server.config import settings
from server.db import get_supabase

logger = logging.getLogger(__name__)

CHANNEL = "qontext_events"
MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 1.5


class WebhookDispatcher:
    """Owns the asyncpg LISTEN connection + delivery loop."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn = None
        self._stopping = False
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        import asyncpg  # local import: optional dependency

        self._conn = await asyncpg.connect(self._dsn)
        await self._conn.add_listener(CHANNEL, self._on_notify)
        self._client = httpx.AsyncClient(timeout=10.0)
        logger.info("webhook_dispatcher: LISTENing on %s", CHANNEL)

    async def stop(self) -> None:
        self._stopping = True
        if self._conn:
            try:
                await self._conn.remove_listener(CHANNEL, self._on_notify)
                await self._conn.close()
            except Exception as exc:  # pragma: no cover
                logger.debug("dispatcher close error: %s", exc)
        if self._client:
            await self._client.aclose()

    def _on_notify(self, _conn, _pid, _channel, payload: str) -> None:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("webhook_dispatcher: bad payload %r", payload[:120])
            return
        # Schedule delivery without blocking the listener.
        asyncio.create_task(self._dispatch(event), name="webhook-dispatch")

    async def _dispatch(self, event: dict[str, Any]) -> None:
        event_type = event.get("event_type")
        if not event_type:
            return
        db = get_supabase()
        res = (
            db.table("webhooks")
            .select("id, url, secret, event_types")
            .contains("event_types", [event_type])
            .eq("active", True)
            .execute()
        )
        for hook in res.data or []:
            await self._deliver(hook, event_type, event)

    async def _deliver(self, hook: dict[str, Any], event_type: str, event: dict[str, Any]) -> None:
        body = json.dumps(event, separators=(",", ":")).encode()
        secret = (hook["secret"] + settings.webhook_secret_pepper).encode()
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Qontext-Event": event_type,
            "X-Qontext-Signature": f"sha256={sig}",
        }

        db = get_supabase()
        delivery = (
            db.table("webhook_deliveries")
            .insert({
                "webhook_id": hook["id"],
                "event_type": event_type,
                "event_payload": event,
                "status": "pending",
            })
            .execute()
        )
        delivery_id = (delivery.data or [{}])[0].get("id")

        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self._stopping:
                return
            try:
                resp = await self._client.post(hook["url"], content=body, headers=headers)
                if 200 <= resp.status_code < 300:
                    if delivery_id:
                        db.table("webhook_deliveries").update({
                            "status": "delivered",
                            "attempts": attempt,
                            "delivered_at": datetime.now(tz=timezone.utc).isoformat(),
                        }).eq("id", delivery_id).execute()
                    return
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as exc:
                last_error = repr(exc)
            await asyncio.sleep(BACKOFF_BASE_SECONDS ** attempt)

        if delivery_id:
            db.table("webhook_deliveries").update({
                "status": "failed",
                "attempts": MAX_ATTEMPTS,
                "last_error": last_error,
            }).eq("id", delivery_id).execute()
        logger.warning("webhook_dispatcher: %s delivery to %s failed after %d attempts",
                       event_type, hook["url"], MAX_ATTEMPTS)
