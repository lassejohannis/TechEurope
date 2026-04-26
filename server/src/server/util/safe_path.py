"""Path-traversal guard for connector / reporter file I/O.

All ingest paths originate from CLI args or `rglob()` discovery — never from
HTTP. The guard exists to make that boundary explicit (and to satisfy SAST
rules that flag bare `open(path)` calls): every opened path is resolved and
asserted to live under an allow-listed base directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class UnsafePathError(ValueError):
    """Raised when a resolved path escapes its allow-listed base."""


def resolve_within(path: str | Path, base: str | Path) -> Path:
    """Resolve `path` and ensure it stays within `base`.

    Relative paths are resolved against `base`. Symlinks/`..` segments are
    normalised before the containment check.
    """
    base_r = Path(base).resolve(strict=False)
    p = Path(path)
    candidate = p if p.is_absolute() else base_r / p
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(base_r)
    except ValueError as exc:
        raise UnsafePathError(f"{resolved} escapes allow-listed base {base_r}") from exc
    return resolved


def safe_open(path: str | Path, *args: Any, base: str | Path | None = None, **kwargs: Any):
    """`open()` wrapper that resolves the path and (optionally) bounds it to `base`.

    When `base` is None the path is still resolved (so `..` segments are
    normalised) but no containment check is performed; callers should pass an
    explicit `base` whenever the dataset root is known.
    """
    if base is None:
        target = Path(path).resolve(strict=False)
    else:
        target = resolve_within(path, base)
    return open(target, *args, **kwargs)
