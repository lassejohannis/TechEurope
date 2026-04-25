"""Shared pytest config — keeps WS-5 tests usable while WS-0 is still in flight."""

from __future__ import annotations

import os

import pytest


def _load_dotenv() -> None:
    """Pick up server/.env so live tests work via plain `pytest`."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(here, ".env"))


_load_dotenv()


def neo4j_creds_or_skip() -> tuple[str, str, str]:
    """Read NEO4J_* from env or skip — WS-5 tests are opt-in until Aura is up."""
    uri = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER") or "neo4j"
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not (uri and password):
        pytest.skip("NEO4J_URI / NEO4J_PASSWORD not set — skipping live Neo4j test")
    return uri, user, password
