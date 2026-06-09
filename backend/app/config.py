"""Application configuration, loaded from environment / .env.

A single ``Settings`` object is the one place that reads the environment, so the
rest of the app depends on typed fields instead of ``os.getenv`` calls.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is two levels up from this file (backend/app/config.py -> repo/).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed view over the environment. See ``.env.example`` for documentation."""

    model_config = SettingsConfigDict(
        # Prefer a repo-root .env, then a backend-local one; real env vars win.
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Gemini / Google GenAI ---
    google_genai_use_vertexai: bool = False
    google_api_key: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"

    # --- Market data ---
    finnhub_api_key: str = ""

    # --- Arize Phoenix ---
    phoenix_collector_endpoint: str = "http://localhost:6006"
    phoenix_project_name: str = "bull-vs-bear"

    # --- Persistence ---
    history_backend: str = "local"  # "local" | "firestore"

    # --- Server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_allow_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        """CORS origins as a list (env holds a comma-separated string)."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def gemini_configured(self) -> bool:
        """True if we have enough to talk to Gemini via the chosen backend."""
        if self.google_genai_use_vertexai:
            return bool(self.google_cloud_project)
        return bool(self.google_api_key)

    @property
    def gemini_backend(self) -> str:
        return "vertexai" if self.google_genai_use_vertexai else "ai-studio"

    def public_status(self) -> dict[str, object]:
        """Non-secret config summary, safe to expose via /health."""
        return {
            "gemini_backend": self.gemini_backend,
            "gemini_model": self.gemini_model,
            "gemini_configured": self.gemini_configured,
            "market_data": "finnhub" if self.finnhub_api_key else "yfinance",
            "history_backend": self.history_backend,
            "phoenix_endpoint": self.phoenix_collector_endpoint,
        }


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
