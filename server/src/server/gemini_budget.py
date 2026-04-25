"""Process-wide budget + rate-limit wrapper for Gemini API calls.

Every Gemini call (embedding, generate_content, structured-output, …) goes
through ``gemini_call(model, fn)``. The wrapper enforces:

1. **Hard cap**: a session-wide max-calls counter. Past the cap, calls return
   None instead of hammering the API.
2. **Cooldown**: when Gemini returns RESOURCE_EXHAUSTED (429), set a
   ``cooldown_until`` timestamp. All subsequent calls during cooldown return
   None — give the rate-limiter time to recover.
3. **Per-minute rolling window**: soft-limit. Calls sleep just long enough
   to stay under the limit (avoids burst 429s).

The wrapper is intentionally chill: it never raises on quota issues, just
returns None so callers degrade gracefully (skip embedding, leave fact
unmined, …). Exceptions other than 429 propagate normally.

Usage:

    from server.gemini_budget import gemini_call, get_budget

    def _embed():
        return client.models.embed_content(model="...", contents="...")

    response = gemini_call("gemini-embedding-001", _embed)
    if response is None:
        return None  # capped or in cooldown
    ...
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from server.config import settings

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class GeminiBudget:
    """Thread-safe singleton tracking Gemini API usage for the current process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls_total: int = 0
        self.calls_skipped: int = 0
        self.calls_per_model: dict[str, int] = {}
        self.cooldown_until: datetime | None = None
        self.recent_call_timestamps: deque[datetime] = deque(maxlen=512)
        # Snapshot config at construction; can be overridden via set_overrides()
        self.hard_cap_total: int = settings.gemini_hard_cap_total
        self.cooldown_seconds: int = settings.gemini_cooldown_seconds
        self.per_minute_limit: int = settings.gemini_per_minute_limit

    # ------------------------------------------------------------------
    # Public read-only state
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "calls_total": self.calls_total,
                "calls_skipped": self.calls_skipped,
                "calls_per_model": dict(self.calls_per_model),
                "hard_cap": self.hard_cap_total,
                "cap_remaining": max(0, self.hard_cap_total - self.calls_total),
                "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
                "in_cooldown": self.in_cooldown(),
                "per_minute_limit": self.per_minute_limit,
                "calls_last_60s": self._calls_in_last_60s(),
            }

    def in_cooldown(self) -> bool:
        return self.cooldown_until is not None and _now() < self.cooldown_until

    def cap_reached(self) -> bool:
        return self.calls_total >= self.hard_cap_total

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _calls_in_last_60s(self) -> int:
        cutoff = _now() - timedelta(seconds=60)
        return sum(1 for t in self.recent_call_timestamps if t > cutoff)

    def _can_call(self, model: str) -> tuple[bool, str]:
        if self.in_cooldown():
            return False, f"cooldown until {self.cooldown_until.isoformat()}"
        if self.cap_reached():
            return False, f"hard cap {self.hard_cap_total} reached"
        return True, ""

    def _wait_for_minute_window(self) -> None:
        """Block briefly to stay under per_minute_limit. Releases lock during sleep."""
        while True:
            with self._lock:
                count = self._calls_in_last_60s()
                if count < self.per_minute_limit:
                    return
            # Sleep ~half a second outside the lock
            time.sleep(0.5)

    def _record_outcome(self, model: str, success: bool, error: str | None = None) -> None:
        with self._lock:
            self.calls_total += 1
            self.calls_per_model[model] = self.calls_per_model.get(model, 0) + 1
            self.recent_call_timestamps.append(_now())
            if not success and error and "RESOURCE_EXHAUSTED" in error:
                self.cooldown_until = _now() + timedelta(seconds=self.cooldown_seconds)
                logger.warning(
                    "Gemini quota exhausted on %s — cooldown until %s",
                    model,
                    self.cooldown_until.isoformat(),
                )

    def _record_skip(self, model: str, reason: str) -> None:
        with self._lock:
            self.calls_skipped += 1
        logger.debug("gemini call to %s skipped: %s", model, reason)


# Process-wide singleton — accessed via gemini_call() / get_budget()
_BUDGET = GeminiBudget()


def get_budget() -> GeminiBudget:
    return _BUDGET


def gemini_call(model: str, fn: Callable[[], Any]) -> Any | None:
    """Run a Gemini API call under the budget.

    Returns the call's return value, or None if the call was skipped due to
    hard cap / cooldown. Exceptions are recorded then re-raised — except
    RESOURCE_EXHAUSTED, which only triggers cooldown and returns None
    (so the calling code doesn't see a stack trace for an expected event).
    """
    allowed, reason = _BUDGET._can_call(model)
    if not allowed:
        _BUDGET._record_skip(model, reason)
        return None

    _BUDGET._wait_for_minute_window()

    try:
        result = fn()
    except Exception as exc:
        msg = str(exc)
        _BUDGET._record_outcome(model, success=False, error=msg)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            return None  # quota — caller should treat as cap-skip
        raise
    _BUDGET._record_outcome(model, success=True)
    return result
