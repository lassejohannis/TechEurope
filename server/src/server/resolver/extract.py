"""Per-source-type candidate extraction.

Walks `source_records.payload` shapes from connectors (email, customer, client,
hr_record, sale, product) and emits ``CandidateEntity`` lists plus pending
fact descriptors. Pending facts use *names* as placeholders for subject/object;
the caller resolves names to entity IDs after entities have been written.

The extractors below cover the deterministic-first cases (hard IDs in payload).
LLM-based extraction (free-form fact mining from email body) is out of scope
for this module — that's WS-3's job via `server.extractors.gemini`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.resolver.cascade import CandidateEntity


@dataclass
class PendingFact:
    """A fact whose subject/object are referenced by canonical_name + entity_type.

    The CLI resolves names → entity IDs after `_persist_entities` is called.
    """

    subject_key: tuple[str, str]  # (entity_type, canonical_name)
    predicate: str
    object_key: tuple[str, str] | None = None  # (entity_type, name) for entity refs
    object_literal: Any | None = None
    confidence: float = 0.95
    extraction_method: str = "rule"


def _domain_from_email(email: str) -> str | None:
    if "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower()


def _company_from_business_name(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip()


# ---------------------------------------------------------------------------
# Per-source-type extractors
# ---------------------------------------------------------------------------


def _extract_email(payload: dict[str, Any]) -> tuple[list[CandidateEntity], list[PendingFact]]:
    sender_name = (payload.get("sender_name") or "").strip()
    sender_email = (payload.get("sender_email") or "").strip().lower()
    sender_emp_id = payload.get("sender_emp_id")
    recipient_name = (payload.get("recipient_name") or "").strip()
    recipient_email = (payload.get("recipient_email") or "").strip().lower()
    recipient_emp_id = payload.get("recipient_emp_id")

    entities: list[CandidateEntity] = []
    facts: list[PendingFact] = []

    domains: dict[str, str] = {}  # email → domain (for company facts)
    for name, email, emp_id in (
        (sender_name, sender_email, sender_emp_id),
        (recipient_name, recipient_email, recipient_emp_id),
    ):
        if not name or not email:
            continue
        attrs = {"email": email}
        if emp_id:
            attrs["emp_id"] = emp_id
        entities.append(CandidateEntity(entity_type="person", canonical_name=name, attrs=attrs))
        if (domain := _domain_from_email(email)):
            domains[email] = domain

    # Companies inferred from email domains (one per unique domain)
    seen_domains: set[str] = set()
    for domain in domains.values():
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        # Use the domain root as canonical name; will be merged via Tier-4 context
        # when an explicit company entity (from CRM) shares the same domain.
        canonical = domain.rsplit(".", 1)[0].title() if "." in domain else domain
        entities.append(
            CandidateEntity(
                entity_type="company",
                canonical_name=canonical,
                attrs={"domain": domain},
            )
        )

    # Facts: works_at(person → company by domain), participated_in(person → thread)
    for name, email in ((sender_name, sender_email), (recipient_name, recipient_email)):
        if not name or not email:
            continue
        domain = domains.get(email)
        if domain:
            company_name = domain.rsplit(".", 1)[0].title() if "." in domain else domain
            facts.append(
                PendingFact(
                    subject_key=("person", name),
                    predicate="works_at",
                    object_key=("company", company_name),
                    confidence=0.85,
                )
            )

    return entities, facts


def _extract_client_or_customer(
    payload: dict[str, Any], source_type: str
) -> tuple[list[CandidateEntity], list[PendingFact]]:
    entities: list[CandidateEntity] = []
    facts: list[PendingFact] = []

    # `customer` records are individual buyers (person), not businesses (`client`).
    if source_type == "customer" and payload.get("customer_name"):
        cust_name = payload["customer_name"].strip().title()
        attrs: dict[str, Any] = {"role": "customer"}
        if cid := payload.get("customer_id"):
            attrs["customer_id"] = str(cid)
        entities.append(
            CandidateEntity(entity_type="person", canonical_name=cust_name, attrs=attrs)
        )
        return entities, facts

    business_name = _company_from_business_name(
        payload.get("business_name") or payload.get("name")
    )
    contact_name = payload.get("contact_person_name") or payload.get("contact_name")
    contact_email = (payload.get("contact_email") or "").strip().lower()
    tax_id = payload.get("tax_id")
    industry = payload.get("industry")
    domain = _domain_from_email(contact_email) if contact_email else None

    if business_name:
        attrs: dict[str, Any] = {}
        if tax_id:
            attrs["tax_id"] = str(tax_id)
        if industry:
            attrs["industry"] = industry
        if domain:
            attrs["domain"] = domain
        attrs["customer_status"] = source_type  # 'customer' or 'client'
        entities.append(
            CandidateEntity(entity_type="company", canonical_name=business_name, attrs=attrs)
        )

    if contact_name and contact_email:
        entities.append(
            CandidateEntity(
                entity_type="person",
                canonical_name=contact_name,
                attrs={"email": contact_email},
            )
        )
        if business_name:
            facts.append(
                PendingFact(
                    subject_key=("person", contact_name),
                    predicate="works_at",
                    object_key=("company", business_name),
                    confidence=0.92,
                )
            )

    return entities, facts


def _extract_hr_record(payload: dict[str, Any]) -> tuple[list[CandidateEntity], list[PendingFact]]:
    name = (payload.get("Name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    emp_id = payload.get("emp_id")
    category = payload.get("category")
    reports_to = payload.get("reports_to")
    level = payload.get("Level")

    entities: list[CandidateEntity] = []
    facts: list[PendingFact] = []

    if not name:
        return entities, facts

    attrs: dict[str, Any] = {}
    if email:
        attrs["email"] = email
    if emp_id:
        attrs["emp_id"] = str(emp_id)
    if category:
        attrs["department"] = category
    if level:
        attrs["level"] = level

    entities.append(CandidateEntity(entity_type="person", canonical_name=name, attrs=attrs))

    # Company from email domain
    if (domain := _domain_from_email(email)):
        canonical_company = domain.rsplit(".", 1)[0].title() if "." in domain else domain
        entities.append(
            CandidateEntity(
                entity_type="company",
                canonical_name=canonical_company,
                attrs={"domain": domain},
            )
        )
        facts.append(
            PendingFact(
                subject_key=("person", name),
                predicate="works_at",
                object_key=("company", canonical_company),
                confidence=0.95,
            )
        )

    # Reports-to fact uses emp_id; we leave it as a literal — a follow-up resolver
    # pass can rewire it once all hr_records have been ingested.
    if reports_to:
        facts.append(
            PendingFact(
                subject_key=("person", name),
                predicate="reports_to_emp_id",
                object_literal=str(reports_to),
                confidence=0.99,
            )
        )

    return entities, facts


def _extract_product(payload: dict[str, Any]) -> tuple[list[CandidateEntity], list[PendingFact]]:
    name = (payload.get("product_name") or payload.get("name") or "").strip()
    if not name:
        return [], []
    attrs = {
        k: payload[k]
        for k in ("product_id", "sku", "category", "price", "currency")
        if payload.get(k) is not None
    }
    return [CandidateEntity(entity_type="product", canonical_name=name, attrs=attrs)], []


def _extract_sale(payload: dict[str, Any]) -> tuple[list[CandidateEntity], list[PendingFact]]:
    # Sales link customer ↔ product; we extract the product reference if available.
    # Customer side is already covered by client/customer extractors.
    entities: list[CandidateEntity] = []
    facts: list[PendingFact] = []

    customer_name = (payload.get("customer_name") or payload.get("client_name") or "").strip()
    product_name = (payload.get("product_name") or "").strip()

    if customer_name and product_name:
        facts.append(
            PendingFact(
                subject_key=("company", customer_name),
                predicate="purchased",
                object_key=("product", product_name),
                confidence=0.98,
            )
        )
    return entities, facts


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


_EXTRACTORS = {
    "email": lambda p: _extract_email(p),
    "client": lambda p: _extract_client_or_customer(p, "client"),
    "customer": lambda p: _extract_client_or_customer(p, "customer"),
    "hr_record": lambda p: _extract_hr_record(p),
    "product": lambda p: _extract_product(p),
    "sale": lambda p: _extract_sale(p),
}


def extract_candidates(
    source_record: dict[str, Any],
) -> tuple[list[CandidateEntity], list[PendingFact]]:
    """Return (entities, pending_facts) extracted from a source_records row."""
    payload = source_record.get("payload") or {}
    source_type = source_record.get("source_type", "")
    fn = _EXTRACTORS.get(source_type)
    if not fn:
        return [], []
    entities, facts = fn(payload)
    # Stamp source_id on every candidate so downstream persisters know provenance.
    sid = source_record.get("id", "")
    for e in entities:
        e.source_id = sid
    return entities, facts
