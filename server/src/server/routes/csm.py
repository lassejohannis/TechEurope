"""CSM-App minimal Query API — reads from Core Context Engine tables.

Maps DB schema (entity_type, attrs, object_id/object_literal, source_id)
to CSM-App frontend types (type, attributes, object, derived_from).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from server.db import get_supabase

router = APIRouter(prefix="/api", tags=["csm-app"])

# Entity types treated as "accounts" in the CSM app
_ACCOUNT_TYPES = ("organization", "company", "customer", "client")


def _health_from_trust(trust_score: float) -> dict[str, Any]:
    score = int(trust_score * 100)
    if score >= 70:
        tier = "green"
    elif score >= 40:
        tier = "yellow"
    else:
        tier = "red"
    return {
        "score": score,
        "tier": tier,
        "factors": [],
        "computed_at": "",
    }


def _map_entity(e: dict[str, Any]) -> dict[str, Any]:
    attrs = e.get("attrs") or e.get("attributes") or {}
    return {
        "id": e["id"],
        "type": e.get("entity_type") or e.get("type") or "organization",
        "canonical_name": e.get("canonical_name") or e["id"],
        "aliases": e.get("aliases") or [],
        "attributes": attrs,
        "status": e.get("status") or "live",
        "created_at": str(e.get("created_at") or ""),
        "updated_at": str(e.get("updated_at") or ""),
        "provenance": e.get("provenance") or [],
    }


def _map_fact(f: dict[str, Any]) -> dict[str, Any]:
    object_id = f.get("object_id")
    object_literal = f.get("object_literal")
    if object_id:
        obj = object_id
        obj_type = "entity"
    elif object_literal is not None:
        obj = object_literal if isinstance(object_literal, (str, int, float, bool)) else str(object_literal)
        obj_type = "string"
    else:
        obj = None
        obj_type = "string"

    source_id = f.get("source_id") or ""
    return {
        "id": f["id"],
        "subject": f.get("subject_id") or "",
        "predicate": f.get("predicate") or "",
        "object": obj,
        "object_type": obj_type,
        "confidence": float(f.get("confidence") or 0),
        "status": f.get("status") or "live",
        "derived_from": [source_id] if source_id else [],
        "qualifiers": {},
        "created_at": str(f.get("valid_from") or f.get("recorded_at") or ""),
        "updated_at": str(f.get("recorded_at") or ""),
        "superseded_by": f.get("superseded_by"),
    }


# ── Accounts ──────────────────────────────────────────────────────────────────

@router.get("/accounts")
def list_accounts() -> list[dict[str, Any]]:
    db = get_supabase()
    rows: list[dict[str, Any]] = []
    for entity_type in _ACCOUNT_TYPES:
        res = (
            db.table("entities")
            .select("id, entity_type, canonical_name, attrs, status")
            .eq("entity_type", entity_type)
            .is_("deleted_at", "null")
            .limit(200)
            .execute()
        )
        rows.extend(res.data or [])

    # fetch trust scores in bulk
    ids = [r["id"] for r in rows]
    trust_map: dict[str, float] = {}
    if ids:
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            t_res = (
                db.table("entity_trust")
                .select("id, trust_score")
                .in_("id", chunk)
                .execute()
            )
            for t in t_res.data or []:
                trust_map[t["id"]] = float(t.get("trust_score") or 0)

    items = []
    for e in rows:
        trust = trust_map.get(e["id"], 0.5)
        health = _health_from_trust(trust)
        tier = health["tier"]
        if tier == "red":
            summary = {"status_label": "At Risk", "why": "Low data coverage.", "impact": "High risk", "next_action": "Schedule review call", "cta_type": "escalation"}
        elif tier == "yellow":
            summary = {"status_label": "Needs Attention", "why": "Some data gaps.", "impact": "Medium risk", "next_action": "Send check-in email", "cta_type": "recovery-email"}
        else:
            summary = {"status_label": "Healthy", "why": "Good fact coverage.", "impact": "Low risk", "next_action": "Schedule QBR", "cta_type": "none"}
        items.append({
            "entity": _map_entity(e),
            "facts": [],
            "key_contacts": [],
            "open_tickets": [],
            "recent_communications": [],
            "health": health,
            "stakeholder_change_detected": False,
            "new_stakeholders": [],
            "executive_summary": summary,
        })
    return items


@router.get("/accounts/{account_id}")
def get_account_card(account_id: str) -> dict[str, Any]:
    db = get_supabase()

    try:
        ent_res = db.table("entities").select("*").eq("id", account_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="account not found")
    if not ent_res.data:
        raise HTTPException(status_code=404, detail="account not found")
    ent = ent_res.data

    facts_res = (
        db.table("facts")
        .select("id, subject_id, predicate, object_id, object_literal, confidence, status, source_id, valid_from, recorded_at, superseded_by")
        .eq("subject_id", account_id)
        .is_("valid_to", "null")
        .execute()
    )
    facts = [_map_fact(f) for f in (facts_res.data or [])]

    # key contacts: persons linked via facts
    contact_ids = [
        f["object"] for f in facts
        if f["object_type"] == "entity" and f["predicate"] in ("contact_person", "primary_contact", "managed_by")
    ]
    key_contacts = []
    if contact_ids:
        c_res = db.table("entities").select("*").in_("id", contact_ids[:10]).execute()
        for c in c_res.data or []:
            key_contacts.append({"entity": _map_entity(c), "role": "contact"})

    # trust / health
    try:
        t_res = db.table("entity_trust").select("trust_score").eq("id", account_id).single().execute()
        trust = float((t_res.data or {}).get("trust_score") or 0.5)
    except Exception:
        trust = 0.5
    health = _health_from_trust(trust)

    # simple executive summary from health tier
    tier = health["tier"]
    if tier == "red":
        summary = {
            "status_label": "At Risk",
            "why": "Low trust score — few confirmed facts.",
            "impact": "High risk of churn",
            "next_action": "Schedule review call",
            "cta_type": "escalation",
        }
    elif tier == "yellow":
        summary = {
            "status_label": "Needs Attention",
            "why": "Moderate engagement; some data gaps.",
            "impact": "Medium risk",
            "next_action": "Send check-in email",
            "cta_type": "recovery-email",
        }
    else:
        summary = {
            "status_label": "Healthy",
            "why": "Strong fact coverage and source diversity.",
            "impact": "Low risk",
            "next_action": "Schedule QBR",
            "cta_type": "none",
        }

    return {
        "entity": _map_entity(ent),
        "facts": facts,
        "key_contacts": key_contacts,
        "open_tickets": [],
        "recent_communications": [],
        "health": health,
        "stakeholder_change_detected": False,
        "new_stakeholders": [],
        "executive_summary": summary,
    }


@router.get("/accounts/{account_id}/insights")
def get_account_insights(account_id: str) -> list[dict[str, Any]]:
    db = get_supabase()
    facts_res = (
        db.table("facts")
        .select("id, predicate, confidence")
        .eq("subject_id", account_id)
        .is_("valid_to", "null")
        .execute()
    )
    facts = facts_res.data or []
    fact_count = len(facts)
    low_conf = sum(1 for f in facts if float(f.get("confidence") or 0) < 0.7)

    insights = []
    if fact_count > 0:
        insights.append({
            "id": f"insight:{account_id}:facts",
            "icon_key": "engagement",
            "headline": f"{fact_count} facts indexed from connected sources",
            "secondary": None,
        })
    if low_conf > 0:
        insights.append({
            "id": f"insight:{account_id}:confidence",
            "icon_key": "sentiment",
            "headline": f"{low_conf} facts have low confidence — review recommended",
            "secondary": "Consider verifying with primary source",
        })
    if not insights:
        insights.append({
            "id": f"insight:{account_id}:empty",
            "icon_key": "engagement",
            "headline": "No facts indexed yet for this account",
            "secondary": None,
        })
    return insights


# ── Briefing ──────────────────────────────────────────────────────────────────

@router.get("/briefing/daily")
def daily_briefing() -> dict[str, Any]:
    db = get_supabase()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Load all accounts
    rows: list[dict[str, Any]] = []
    for entity_type in _ACCOUNT_TYPES:
        res = (
            db.table("entities")
            .select("id, entity_type, canonical_name, attrs")
            .eq("entity_type", entity_type)
            .is_("deleted_at", "null")
            .limit(200)
            .execute()
        )
        rows.extend(res.data or [])

    # Fetch trust scores
    ids = [r["id"] for r in rows]
    trust_map: dict[str, float] = {}
    if ids:
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            t_res = db.table("entity_trust").select("id, trust_score").in_("id", chunk).execute()
            for t in t_res.data or []:
                trust_map[t["id"]] = float(t.get("trust_score") or 0)

    items = []
    for e in rows:
        trust = trust_map.get(e["id"], 0.3)
        health = _health_from_trust(trust)
        tier = health["tier"]
        attrs = e.get("attrs") or {}

        if tier == "red":
            signal = "sentiment_drop"
            headline = f"{e.get('canonical_name', e['id'])} needs attention"
            detail = "Low data coverage — few facts confirmed."
            action = "Schedule a review call"
            cta = "escalation"
        elif tier == "yellow":
            signal = "engagement_gap"
            headline = f"{e.get('canonical_name', e['id'])} — engagement gap detected"
            detail = "Moderate fact coverage; some data gaps remain."
            action = "Send a check-in email"
            cta = "recovery-email"
        else:
            signal = "upsell_signal"
            headline = f"{e.get('canonical_name', e['id'])} — healthy account"
            detail = "Strong fact coverage and source diversity."
            action = "Schedule QBR"
            cta = "none"

        items.append({
            "id": f"briefing:{e['id']}",
            "account_id": e["id"],
            "account_name": e.get("canonical_name") or e["id"],
            "priority": tier,
            "signal_type": signal,
            "segment": "Mid-Market",
            "revenue_impact": "—",
            "revenue_impact_eur": 0,
            "renewal_date": attrs.get("renewal_date") or None,
            "headline": headline,
            "detail": detail,
            "recommended_action": action,
            "evidence_fact_ids": [],
            "communication_id": None,
            "created_at": now,
            "cta_type": cta,
        })

    # Sort: red first, then yellow, then green
    order = {"red": 0, "yellow": 1, "green": 2}
    items.sort(key=lambda x: order.get(x["priority"], 3))

    return {
        "generated_at": now,
        "items": items,
        "summary": f"{len(rows)} accounts · {len([i for i in items if i['priority'] == 'red'])} need attention",
    }


@router.get("/briefing/summaries")
def card_summaries() -> dict[str, Any]:
    return {}


# ── Generate (stubs — MCP/LLM can be wired here) ─────────────────────────────

@router.post("/generate/recovery-email")
def generate_recovery_email() -> dict[str, Any]:
    return {
        "account_id": "", "contact_id": "", "to": "",
        "subject": "Checking in — how can we help?",
        "body": "Hi,\n\nI wanted to reach out personally to check in...\n\nBest,",
        "generated_at": "", "variation": 1,
    }


@router.post("/generate/stakeholder-intro")
def generate_stakeholder_intro() -> dict[str, Any]:
    return {
        "account_id": "", "contact_id": "", "to": "",
        "subject": "Introduction",
        "body": "Hi,\n\nI wanted to introduce myself...\n\nBest,",
        "generated_at": "", "variation": 1,
    }


@router.post("/generate/escalation-briefing")
def generate_escalation_briefing() -> dict[str, Any]:
    return {
        "account_id": "", "health_summary": "Account needs attention.",
        "evidence_bullets": [], "suggested_owners": [], "generated_at": "",
    }
