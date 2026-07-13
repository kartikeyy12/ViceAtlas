"""
config.py — Central configuration loader.

WHAT THIS FILE DOES:
    Loads environment variables from .env and exposes them as typed Python objects.
    Every other module imports from here instead of calling os.getenv() directly.

WHY IT'S STRUCTURED THIS WAY:
    - One place to change = one place to break. If a scraper needs a new setting,
      add it here and every scraper gets it automatically.
    - Pydantic validates types at startup. If you forget to set ANTHROPIC_API_KEY,
      the app crashes immediately with a clear error instead of failing mysteriously
      halfway through a scraper run.
    - Switching from GTA 5 to GTA 6 is just editing .env — this file doesn't change.

HOW TO ADD A NEW SETTING:
    1. Add it to .env.example (for documentation).
    2. Add a field to the Settings class below.
    3. Use it anywhere by importing: from ingestion.config import settings
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Figure out where .env lives: same folder as this file, go up to ingestion-layer/
_ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    """
    Every setting is defined here with a type, default, and description.
    Pydantic reads these from the .env file automatically.
    """

    # Tell Pydantic where to look for .env and how to parse it
    model_config = SettingsConfigDict(
        env_file=_ENV_PATH,      # path to .env file
        env_file_encoding="utf-8",
        extra="ignore",         # ignore extra vars in .env we don't define here
    )

    # -------------------------------------------------------------------------
    # Reddit
    # -------------------------------------------------------------------------
    reddit_client_id: str = Field(..., description="Reddit app client ID")
    reddit_client_secret: str = Field(..., description="Reddit app client secret")
    reddit_user_agent: str = Field(
        default="gta-hub-ingestion/0.1.0",
        description="Identifies your app to Reddit's API"
    )

     # -------------------------------------------------------------------------
    # Google Gemini (LLM extraction)
    # -------------------------------------------------------------------------
    gemini_api_key: str = Field(..., description="API key for Google Gemini LLM extraction")
    
    # -------------------------------------------------------------------------
    # YouTube (optional — only needed if you want metadata beyond transcripts)
    # -------------------------------------------------------------------------
    youtube_api_key: str | None = Field(
        default=None,
        description="Google Cloud API key for YouTube Data API v3 (optional)"
    )

    # -------------------------------------------------------------------------
    # Ingestion behaviour
    # -------------------------------------------------------------------------
    test_mode_limit: int = Field(
        default=5,
        description="Max items to pull in test mode"
    )
    catchup_days: int = Field(
        default=7,
        description="How many days back to pull on a catch-up run"
    )
    subreddits: str = Field(
        default="GTA5",
        description="Comma-separated list of subreddits to monitor"
    )
    youtube_sources: str = Field(
        default="",
        description="Comma-separated list of YouTube channel/video IDs"
    )
    rss_feeds: str = Field(
        default="",
        description="Comma-separated list of RSS/Atom feed URLs"
    )

    # -------------------------------------------------------------------------
    # Deduplicator
    # -------------------------------------------------------------------------
    dedup_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Cosine-similarity threshold above which items are considered duplicates"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="HuggingFace sentence-transformer model name (runs locally)"
    )

    # -------------------------------------------------------------------------
    # Helpers (computed properties, not from .env)
    # -------------------------------------------------------------------------
    @property
    def subreddit_list(self) -> list[str]:
        """Splits the comma-separated string into a clean list."""
        return [s.strip() for s in self.subreddits.split(",") if s.strip()]

    @property
    def youtube_source_list(self) -> list[str]:
        """Splits the comma-separated string into a clean list."""
        return [s.strip() for s in self.youtube_sources.split(",") if s.strip()]

    @property
    def rss_feed_list(self) -> list[str]:
        """Splits the comma-separated string into a clean list."""
        return [s.strip() for s in self.rss_feeds.split(",") if s.strip()]


# Singleton instance — import this everywhere you need config.
# It loads once when the module is first imported, then reuses the same object.
settings = Settings()