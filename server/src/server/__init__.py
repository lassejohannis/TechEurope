"""Tech Europe Hack 2026 — Qontext track backend.

Two layers behind one process:
- Core Context Engine (use-case agnostic)
- Revenue Intelligence App (consumes Core via the Query API)

The hard separation rule lives at the import boundary: nothing in
`server.core.*` may import from `server.apps.*`.
"""

import os as _os
import ssl as _ssl


def _ensure_ssl_cert_bundle() -> None:
    """Fall back to `certifi`'s CA bundle if the OS bundle is missing.

    macOS python.org installs ship without running "Install Certificates.command",
    leaving `ssl.get_default_verify_paths()` pointing at a non-existent file.
    Without this, every TLS client (Neo4j Aura, Supabase, Gemini) breaks with
    SSLCertVerificationError. Idempotent — only sets SSL_CERT_FILE if not
    already configured and the default path is missing.
    """
    if _os.environ.get("SSL_CERT_FILE"):
        return
    cafile = _ssl.get_default_verify_paths().openssl_cafile
    if cafile and _os.path.exists(cafile):
        return
    try:
        import certifi
    except ModuleNotFoundError:
        return
    _os.environ["SSL_CERT_FILE"] = certifi.where()


_ensure_ssl_cert_bundle()

__version__ = "0.1.0"
