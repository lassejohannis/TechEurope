from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


_NUM_RE = re.compile(r"[^0-9.]+")


def parse_currency(value: str | float | int | None) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # Remove currency symbols and group separators
    s = _NUM_RE.sub("", s.replace(",", ""))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_percent(value: str | float | int | None) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date_iso(value: str | None) -> Optional[str]:
    if not value:
        return None
    s = value.strip()
    # Try a few common patterns
    patterns = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(s, p)
            return dt.date().isoformat()
        except Exception:
            continue
    # Fallback: return as-is
    return s

