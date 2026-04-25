"""Per-source trust weighting — loads config/source_trust_weights.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "source_trust_weights.yaml"
_DEFAULT_WEIGHT = 0.5


@lru_cache(maxsize=1)
def _load_weights() -> dict[str, float]:
    try:
        import yaml  # type: ignore
        with open(_CONFIG_PATH) as f:
            raw = yaml.safe_load(f)
        return {k: float(v) for k, v in (raw or {}).items()}
    except Exception:
        return {}


def get_source_weight(source_type: str) -> float:
    """Return trust weight for a source type (0.0–1.0). Defaults to 0.5."""
    return _load_weights().get(source_type, _DEFAULT_WEIGHT)


def authority_score(confidence: float, source_type: str) -> float:
    """Combined authority score used in auto-resolution conflict resolution."""
    return confidence * get_source_weight(source_type)
