"""Pioneer fine-tuned extractor (WS-3 Tier 3.5).

Stays a stub until the fine-tune job in `docs/ws3-pioneer-finetune.md` finishes
and we have a model id. After that, fill in `_call_pioneer` and flip
`AVAILABLE = True`.

Contract: `extract(text, source_type)` must return the same `ExtractionResult`
shape as `extractors.gemini.extract` so the cascade can swap them transparently.
"""

from __future__ import annotations

import os

from server.extractors.schemas import ExtractionResult

#: Set to True once the fine-tuned model is deployed and PIONEER_MODEL_ID is configured.
AVAILABLE = bool(os.environ.get("PIONEER_MODEL_ID"))


def extract(text: str, source_type: str = "unknown") -> ExtractionResult | None:
    """Return None when Pioneer is not configured — caller falls back to Gemini.

    The model id is read from the env at call time so a teammate can flip it
    on without restarting the server.
    """
    model_id = os.environ.get("PIONEER_MODEL_ID")
    if not model_id:
        return None
    return _call_pioneer(model_id, text, source_type)


def _call_pioneer(model_id: str, text: str, source_type: str) -> ExtractionResult:  # noqa: ARG001
    """Real Pioneer inference call. Implement once the fine-tune is done.

    Per `docs/ws3-pioneer-finetune.md`: hit the Pioneer inference endpoint with
    the model id, parse the response into ExtractionResult.
    """
    raise NotImplementedError(
        "Pioneer inference not wired yet — see docs/ws3-pioneer-finetune.md"
    )
