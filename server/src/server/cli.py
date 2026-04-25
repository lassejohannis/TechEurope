"""CLI entry: `uv run server` starts the FastAPI dev server."""

from __future__ import annotations

import uvicorn

from server.config import settings


def main() -> None:
    uvicorn.run(
        "server.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
