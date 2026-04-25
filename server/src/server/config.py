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

    # Supabase (new API key naming: publishable replaces anon, secret replaces service_role)
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""

    # Gemini (Google DeepMind partner)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Neo4j (read-only projection — WS-5)
    # Empty `neo4j_uri` disables the projection worker; the app stays Postgres-only.
    # `neo4j_username` matches the Aura .env convention.
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_password)

    # Pioneer (WS-3 — optional, cascade falls back to Gemini when not set)
    pioneer_api_key: str = ""
    pioneer_model_id: str = ""


settings = Settings()
