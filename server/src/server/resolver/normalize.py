"""Normalize entity names before matching — strip suffixes, collapse whitespace."""

from __future__ import annotations

import re

_COMPANY_SUFFIXES = re.compile(
    r'\b(inc|ltd|gmbh|bv|llc|corp|co|ag|sa|plc|srl|pvt|pty|nv|cv)\b\.?',
    flags=re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = _COMPANY_SUFFIXES.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_email(email: str) -> str:
    return email.lower().strip()


def email_domain(email: str) -> str | None:
    parts = email.rsplit("@", 1)
    return parts[1].lower() if len(parts) == 2 else None
