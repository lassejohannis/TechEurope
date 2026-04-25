"""Thin JSONata evaluator wrapper used by the generic mapping engine.

JSONata lets the AI-generated mapping configs express:
  - simple field access:        ``reporter.display_name``
  - lowercased canonical names: ``$lowercase(reporter.display_name)``
  - email-domain extraction:    ``$substringAfter(reporter.email, "@")``
  - conditionals:               ``status = 'open' ? 'live' : 'archived'``

We deliberately swallow evaluation errors (return None) so a malformed
mapping never crashes the resolver — it just emits no value for that field.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=512)
def _compile(expression: str):
    from jsonata import Jsonata

    return Jsonata(expression)


def jeval(expression: str | None, payload: dict[str, Any]) -> Any:
    """Evaluate a JSONata expression against a payload. Returns None on error.

    A blank/None expression returns None (treated as "this field is not mapped").
    """
    if not expression:
        return None
    try:
        compiled = _compile(expression)
        return compiled.evaluate(payload)
    except Exception as exc:
        logger.debug("jsonata eval failed for %r: %s", expression[:60], exc)
        return None


def jstr(expression: str | None, payload: dict[str, Any]) -> str | None:
    """Like jeval but coerces the result to a stripped string (or None)."""
    val = jeval(expression, payload)
    if val is None:
        return None
    if isinstance(val, str):
        s = val.strip()
        return s or None
    return str(val).strip() or None
