from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fact_id(subject_id: str, predicate: str, obj: Any, derived_from: list[str]) -> str:
    payload = {
        "s": subject_id,
        "p": predicate,
        "o": obj,
        "d": sorted(derived_from),
    }
    h = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"fact:{h}"

