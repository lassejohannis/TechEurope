from __future__ import annotations

from server.resolver.extract import extract_candidates


def test_email_extract_builds_communication_and_participant_edges():
    source_record = {
        "id": "email:test-1",
        "source_type": "email",
        "payload": {
            "email_id": "mail-1",
            "thread_id": "THR_1",
            "subject": "Quarterly Review",
            "sender_name": "Ravi Kumar",
            "sender_email": "ravi.kumar@inazuma.com",
            "recipient_name": "Rohan Varma",
            "recipient_email": "rohan.varma@inazuma.com",
            "body": "Hi Rohan, I synced with Deepa Singh yesterday.",
        },
    }

    entities, facts = extract_candidates(source_record)

    names = {(e.entity_type, e.canonical_name) for e in entities}
    assert ("communication", "Quarterly Review") in names

    participant_facts = [f for f in facts if f.predicate == "participant_in"]
    assert len(participant_facts) == 2
    assert all(f.derivation == "rule:email_thread" for f in participant_facts)

    mention_facts = [f for f in facts if f.predicate == "mentions"]
    assert mention_facts, "email body mention should generate a mentions fact"
    assert mention_facts[0].subject_key == ("communication", "Quarterly Review")
    assert mention_facts[0].derivation == "llm:email_body_extract"


def test_hr_extract_reports_to_literal_derivation():
    source_record = {
        "id": "hr:test-1",
        "source_type": "hr_record",
        "payload": {
            "Name": "Raj Patel",
            "email": "raj.patel@inazuma.com",
            "emp_id": "emp_0431",
            "reports_to": "emp_0100",
        },
    }

    _, facts = extract_candidates(source_record)
    reports = [f for f in facts if f.predicate == "reports_to_emp_id"]
    assert len(reports) == 1
    assert reports[0].object_literal == "emp_0100"
    assert reports[0].derivation == "rule:hr_reports_to_literal"
