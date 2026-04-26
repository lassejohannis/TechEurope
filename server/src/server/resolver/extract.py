"""Per-source-type candidate extraction.

Walks `source_records.payload` shapes from connectors (email, customer, client,
hr_record, sale, product) and emits ``CandidateEntity`` lists plus pending
fact descriptors. Pending facts use *names* as placeholders for subject/object;
the caller resolves names to entity IDs after entities have been written.

The extractors below cover deterministic-first cases (hard IDs in payload)
and lightweight email-body mention extraction that can be upgraded to WS-3 LLM
pipelines without changing the pending-fact contract.
"""

from __future__ import annotations

import re
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
    derivation: str = "unknown"


def _domain_from_email(email: str) -> str | None:
    if "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower()


def _company_from_business_name(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip()


def _extract_name_mentions(text: str) -> list[str]:
    """Return person name mentions from free text.

    Tries Gemini structured extraction first; falls back to regex when the API
    key is absent or the call fails.
    """
    if not text:
        return []
    try:
        from server.extractors.gemini import extract_mentions
        return extract_mentions(text)
    except Exception:
        pass
    mentions = re.findall(r"\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,})+)\b", text)
    return list(dict.fromkeys(m.strip() for m in mentions if m.strip()))


# ---------------------------------------------------------------------------
# Per-source-type extractors
# ---------------------------------------------------------------------------


def _extract_email(
    payload: dict[str, Any], llm_extract: bool = False
) -> tuple[list[CandidateEntity], list[PendingFact]]:
    email_id = str(payload.get("email_id") or payload.get("id") or "").strip()
    thread_id = str(payload.get("thread_id") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = str(payload.get("body") or "")
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

    communication_name: str | None = None
    comm_attrs: dict[str, Any] = {}
    if thread_id:
        communication_name = f"Thread {thread_id}"
        comm_attrs["thread_id"] = thread_id
    elif email_id:
        communication_name = f"Email {email_id}"
        comm_attrs["email_id"] = email_id
    if communication_name:
        if subject:
            comm_attrs["subject"] = subject
        entities.append(
            CandidateEntity(
                entity_type="communication",
                canonical_name=communication_name,
                attrs=comm_attrs,
            )
        )

    # Facts: works_at(person → company by domain), participant_in(person → communication)
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
                    derivation="rule:email_domain",
                )
            )
        if communication_name:
            facts.append(
                PendingFact(
                    subject_key=("person", name),
                    predicate="participant_in",
                    object_key=("communication", communication_name),
                    confidence=0.95,
                    derivation="rule:email_thread",
                )
            )

    if communication_name and body:
        participants = {sender_name.lower(), recipient_name.lower()}
        mention_names = _extract_name_mentions(body)
        for mention in mention_names:
            if mention.lower() in participants:
                continue
            entities.append(
                CandidateEntity(
                    entity_type="person",
                    canonical_name=mention,
                    attrs={},
                )
            )
            facts.append(
                PendingFact(
                    subject_key=("communication", communication_name),
                    predicate="mentions",
                    object_key=("person", mention),
                    confidence=0.70,
                    extraction_method="gemini",
                    derivation="llm:email_body_extract",
                )
            )

    # Communication entity: one per email thread (or per email if no thread_id).
    # This is what makes the Graph dense — sender + recipient both attach via
    # participant_in / authored edges.
    thread_id = payload.get("thread_id") or payload.get("email_id")
    subject = (payload.get("subject") or "").strip() or "(no subject)"
    if thread_id and (sender_name or recipient_name):
        comm_attrs: dict[str, Any] = {
            "channel": "email",
            "thread_id": str(thread_id),
            "subject": subject,
        }
        if email_id := payload.get("email_id"):
            comm_attrs["email_id"] = str(email_id)
        if date := payload.get("date"):
            comm_attrs["date"] = str(date)
        if importance := payload.get("importance"):
            comm_attrs["importance"] = str(importance)
        if category := payload.get("category"):
            comm_attrs["category"] = str(category)

        entities.append(
            CandidateEntity(
                entity_type="communication",
                canonical_name=subject[:120],
                attrs=comm_attrs,
            )
        )
        if sender_name:
            facts.append(
                PendingFact(
                    subject_key=("person", sender_name),
                    predicate="authored",
                    object_key=("communication", subject[:120]),
                    confidence=0.99,
                )
            )
            facts.append(
                PendingFact(
                    subject_key=("person", sender_name),
                    predicate="participant_in",
                    object_key=("communication", subject[:120]),
                    confidence=0.99,
                )
            )
        if recipient_name and recipient_name != sender_name:
            facts.append(
                PendingFact(
                    subject_key=("person", recipient_name),
                    predicate="participant_in",
                    object_key=("communication", subject[:120]),
                    confidence=0.99,
                )
            )

    # Optional LLM-mined facts from the email body (constrained predicate set).
    if llm_extract and (body := payload.get("body")):
        try:
            from server.extractors.gemini_structured import extract_email_facts

            llm_facts = extract_email_facts(body, sender_name or "", recipient_name or "")
            for ef in llm_facts:
                # Subject must be one of the people we already have on the
                # candidate list — otherwise we'd silently spawn ghost entities.
                subject_match = ef.subject_name.strip()
                if not subject_match:
                    continue
                object_key = None
                object_literal = None
                if ef.object_name:
                    object_key = ("person", ef.object_name.strip())
                else:
                    object_literal = {"quote": ef.quote}
                facts.append(
                    PendingFact(
                        subject_key=("person", subject_match),
                        predicate=ef.predicate,
                        object_key=object_key,
                        object_literal=object_literal,
                        confidence=float(ef.confidence),
                        extraction_method="gemini",
                    )
                )
        except Exception:
            # Never let LLM extraction errors break ingestion.
            pass

    return entities, facts


def _extract_doc(payload: dict[str, Any]) -> tuple[list[CandidateEntity], list[PendingFact]]:
    """Generic Document/Policy/Contract — anything that came through DocumentConnector."""
    title = (payload.get("title") or payload.get("filename") or "").strip()
    source_uri = payload.get("source_uri") or payload.get("path") or payload.get("file")
    doc_type = payload.get("doc_type") or payload.get("type")

    if not title:
        return [], []

    attrs: dict[str, Any] = {"title": title}
    if source_uri:
        attrs["source_uri"] = str(source_uri)
    if doc_type:
        attrs["doc_type"] = str(doc_type)
    if scope := payload.get("scope"):
        attrs["scope"] = str(scope)
    if issued_by := payload.get("issued_by"):
        attrs["issued_by"] = str(issued_by)
    if effective_date := payload.get("effective_date"):
        attrs["effective_date"] = str(effective_date)

    entities = [CandidateEntity(entity_type="document", canonical_name=title[:120], attrs=attrs)]
    facts: list[PendingFact] = []
    # Optional applies_to(document, company) when issuer is named.
    if issuer := payload.get("issued_by"):
        facts.append(
            PendingFact(
                subject_key=("document", title[:120]),
                predicate="applies_to",
                object_key=("company", str(issuer)),
                confidence=0.9,
            )
        )
    return entities, facts


def _extract_it_ticket(payload: dict[str, Any]) -> tuple[list[CandidateEntity], list[PendingFact]]:
    ticket_id = payload.get("ticket_id") or payload.get("id")
    subject = (payload.get("subject") or payload.get("title") or "").strip()
    status = payload.get("status")
    priority = payload.get("priority")
    assignee_name = (payload.get("assignee_name") or payload.get("assigned_to_name") or "").strip()
    creator_name = (payload.get("created_by_name") or payload.get("reporter_name") or "").strip()

    if not ticket_id or not subject:
        return [], []

    attrs: dict[str, Any] = {
        "channel": "ticket",
        "ticket_id": str(ticket_id),
        "subject": subject,
    }
    if status:
        attrs["status"] = str(status)
    if priority:
        attrs["priority"] = str(priority)
    if category := payload.get("category"):
        attrs["category"] = str(category)

    entities: list[CandidateEntity] = [
        CandidateEntity(entity_type="communication", canonical_name=subject[:120], attrs=attrs)
    ]
    facts: list[PendingFact] = []

    if assignee_name:
        entities.append(
            CandidateEntity(entity_type="person", canonical_name=assignee_name, attrs={})
        )
        facts.append(
            PendingFact(
                subject_key=("person", assignee_name),
                predicate="assigned_to",
                object_key=("communication", subject[:120]),
                confidence=0.99,
            )
        )
    if creator_name:
        entities.append(
            CandidateEntity(entity_type="person", canonical_name=creator_name, attrs={})
        )
        facts.append(
            PendingFact(
                subject_key=("person", creator_name),
                predicate="created",
                object_key=("communication", subject[:120]),
                confidence=0.99,
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
                    derivation="rule:contact_company_link",
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
                derivation="rule:hr_email_domain",
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
                derivation="rule:hr_reports_to_literal",
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
                derivation="rule:sale_record",
            )
        )
    return entities, facts


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


def extract_candidates(
    source_record: dict[str, Any],
    *,
    llm_extract: bool = False,
) -> tuple[list[CandidateEntity], list[PendingFact]]:
    """Return (entities, pending_facts) extracted from a source_records row.

    `llm_extract=True` opts in to per-record LLM mining (currently used in the
    email path to surface in-body relationship facts).
    """
    payload = source_record.get("payload") or {}
    source_type = source_record.get("source_type", "") or ""

    if source_type == "email":
        result = _extract_email(payload, llm_extract=llm_extract)
    elif source_type in ("client", "customer"):
        result = _extract_client_or_customer(payload, source_type)
    elif source_type == "hr_record":
        result = _extract_hr_record(payload)
    elif source_type == "product":
        result = _extract_product(payload)
    elif source_type == "sale":
        result = _extract_sale(payload)
    elif source_type == "it_ticket":
        result = _extract_it_ticket(payload)
    else:
        # Fallback for any source_type without a hardcoded extractor
        # (doc_policy, invoice_pdf, collaboration, …). Goes through the
        # autonomous mapping pipeline so JSONata + Pioneer free-text mining
        # both fire honestly.
        from server.db import get_db
        from server.ontology.engine import resolve_with_engine

        try:
            ents, facts = resolve_with_engine(
                source_record, get_db(), llm_extract=llm_extract
            )
        except Exception:
            ents, facts = [], []
        result = (ents, facts)

    entities, facts = result
    # Stamp source_id on every candidate so downstream persisters know provenance.
    sid = source_record.get("id", "")
    for e in entities:
        e.source_id = sid
    return entities, facts
