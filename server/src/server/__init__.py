"""Tech Europe Hack 2026 — Qontext track backend.

Two layers behind one process:
- Core Context Engine (use-case agnostic)
- Revenue Intelligence App (consumes Core via the Query API)

The hard separation rule lives at the import boundary: nothing in
`server.core.*` may import from `server.apps.*`.
"""

__version__ = "0.1.0"
