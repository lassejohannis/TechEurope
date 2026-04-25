"""POST /webhooks/source-change — Source-Change Webhook (Req 10.1).

Receives change events from external systems or the internal FS-watcher.
Marks dependent facts as needs_refresh=true for lazy re-derivation on next read.

Callers:
  - Internal polling loop (mock connectors watching data/ directory)
  - External push from future real connectors (CRM, HR system, etc.)
  - Manual re-ingest triggers via CLI or admin UI

Change detection logic:
  - "created"  → source not yet in DB; no-op (ingest first via POST /ingest)
  - "updated"  → compare content_hash; mark active facts needs_refresh if hash changed
  - "deleted"  → log deletion; DB cascade constraint handles fact cleanup

Returns 202 Accepted in all cases — senders should not retry based on fact-count.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SourceChangePayload(BaseModel):
    source_id: str
    source_type: str
    change_type: Literal["created", "updated", "deleted"]
    content_hash: str | None = None
    metadata: dict[str, Any] = {}


class SourceChangeReceipt(BaseModel):
    event_id: str
    received_at: datetime
    status: Literal["accepted", "noop"]
    source_id: str
    needs_refresh_count: int
    message: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/source-change", response_model=SourceChangeReceipt, status_code=202)
def source_change_webhook(payload: SourceChangePayload, db=Depends(get_db)):
    """Accept a source-change event and schedule dependent facts for re-derivation.

    Always returns 202 — callers must not use HTTP status to judge fact-level outcomes.
    """
    event_id = str(uuid.uuid4())
    received_at = datetime.now(tz=timezone.utc)

    try:
        sr_res = (
            db.table("source_records")
            .select("id, content_hash")
            .eq("source_id", payload.source_id)
            .execute()
        )
        source_rows = sr_res.data or []

        if not source_rows:
            logger.info("Webhook: source %s not in DB yet (change_type=%s)", payload.source_id, payload.change_type)
            return SourceChangeReceipt(
                event_id=event_id,
                received_at=received_at,
                status="noop",
                source_id=payload.source_id,
                needs_refresh_count=0,
                message="Source not found in DB — ingest first via POST /ingest",
            )

        if payload.change_type == "deleted":
            logger.info("Webhook: deleted %s — DB cascade will handle facts", payload.source_id)
            return SourceChangeReceipt(
                event_id=event_id,
                received_at=received_at,
                status="accepted",
                source_id=payload.source_id,
                needs_refresh_count=0,
                message="Deletion noted; ON DELETE CASCADE handles dependent facts",
            )

        # "created" or "updated": mark active facts needs_refresh where hash changed
        needs_refresh_count = 0
        for row in source_rows:
            sr_id = str(row["id"])
            existing_hash = row.get("content_hash")

            if payload.content_hash and existing_hash and payload.content_hash == existing_hash:
                logger.debug("Webhook: hash unchanged for %s — no refresh needed", sr_id)
                continue

            res = (
                db.table("facts")
                .update({"needs_refresh": True})
                .eq("source_id", sr_id)
                .is_("valid_to", "null")
                .execute()
            )
            refreshed = len(res.data or [])
            needs_refresh_count += refreshed
            logger.info("Webhook: marked %d facts needs_refresh for source_record %s", refreshed, sr_id)

            if payload.content_hash and payload.content_hash != existing_hash:
                db.table("source_records").update(
                    {"content_hash": payload.content_hash}
                ).eq("id", sr_id).execute()

        message = (
            f"Marked {needs_refresh_count} active facts for re-derivation"
            if needs_refresh_count > 0
            else "No active facts required refresh (hash unchanged or no facts found)"
        )

        return SourceChangeReceipt(
            event_id=event_id,
            received_at=received_at,
            status="accepted",
            source_id=payload.source_id,
            needs_refresh_count=needs_refresh_count,
            message=message,
        )

    except Exception as exc:
        logger.exception("Webhook processing error: %s", exc)
        return SourceChangeReceipt(
            event_id=event_id,
            received_at=received_at,
            status="accepted",
            source_id=payload.source_id,
            needs_refresh_count=0,
            message=f"Event received but processing error: {exc!s}",
        )
