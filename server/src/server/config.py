"""Runtime config loaded from .env / environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # FastAPI
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_cors_origins: list[str] = ["http://localhost:5173"]

    # Supabase
    supabase_url: str = ""
    supabase_publishable_key: str = ""   # SUPABASE_PUBLISHABLE_KEY (anon)
    supabase_secret_key: str = ""        # SUPABASE_SECRET_KEY (service_role)
    # legacy alias — kept so old code that reads supabase_service_key still works
    supabase_service_key: str = ""

    # Gemini (Google DeepMind partner)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Neo4j Aura (WS-5 graph projection)
    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # Pioneer API (WS-4)
    pioneer_api_key: str = ""


settings = Settings()
