"""Runtime config loaded from .env / environment variables."""

from __future__ import annotations

from pydantic import AliasChoices, Field
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

    # Supabase. Field names match existing usage (anon/service); env vars accept
    # both the new Supabase naming (publishable/secret, sb_publishable_..., sb_secret_...)
    # and the legacy names. Tokens go in .env as SUPABASE_PUBLISHABLE_KEY /
    # SUPABASE_SECRET_KEY for fresh setups.
    supabase_url: str = ""
    supabase_anon_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY"),
    )
    supabase_service_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SERVICE_KEY", "SUPABASE_SECRET_KEY"),
    )

    @property
    def supabase_secret_key(self) -> str:
        """Read-only alias for new naming; consumers should prefer this."""
        return self.supabase_service_key

    @property
    def supabase_publishable_key(self) -> str:
        """Read-only alias for new naming."""
        return self.supabase_anon_key

    # Gemini (Google DeepMind partner)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Neo4j (read-only projection — WS-5)
    # Empty `neo4j_uri` disables the projection worker; the app stays Postgres-only.
    # Accepts both NEO4J_USER (default) and NEO4J_USERNAME (Aura .env convention).
    neo4j_uri: str = ""
    neo4j_user: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_USER", "NEO4J_USERNAME"),
    )
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_password)

    @property
    def neo4j_username(self) -> str:
        """Backward-compatible alias for code still expecting neo4j_username."""
        return self.neo4j_user

    # Pioneer (WS-3 — optional, cascade falls back to Gemini when not set)
    pioneer_api_key: str = ""
    pioneer_model_id: str = ""


settings = Settings()
