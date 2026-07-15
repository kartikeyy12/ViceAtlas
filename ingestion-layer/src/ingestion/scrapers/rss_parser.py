"""
rss_parser.py — Parses RSS/Atom feeds into structured entries.

WHAT THIS FILE DOES:
    Reads an RSS or Atom feed URL, parses entries into clean dicts with
    title, date, body, and link fields.

RATE LIMITS / COST:
    - RSS is just HTTP GET — no API keys, no rate limits beyond politeness.
    - Use a reasonable delay between feeds if you add many.

HOW TO RUN:
    uv run scripts/run_rss_test.py

HOW TO SWITCH TO GTA 6 LATER:
    Change RSS_FEEDS in .env. This file doesn't change.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import feedparser

from ingestion.config import settings
from ingestion.utils.logger import get_logger

logger = get_logger(__name__)


def _parse_date(entry) -> str | None:
    """
    Extracts a standardized ISO date from an RSS entry.
    feedparser provides multiple date fields — we try the most reliable ones.
    """
    # feedparser gives a struct_time or a string depending on the feed
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return None


def _entry_to_dict(entry) -> dict:
    """
    Converts a feedparser entry into our standard raw-data dict.
    """
    return {
        "source": "rss",
        "source_id": entry.get("id") or entry.get("guid") or entry.get("link"),
        "source_url": entry.get("link"),
        "title": entry.get("title", "").strip(),
        "summary": entry.get("summary", "").strip(),
        "body": entry.get("content", [{}])[0].get("value", "") if entry.get("content") else entry.get("summary", ""),
        "author": entry.get("author"),
        "published": _parse_date(entry),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_feeds(
    feed_urls: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Parses configured RSS/Atom feeds and returns structured entries.

    Args:
        feed_urls: Override list of feed URLs. Defaults to RSS_FEEDS from .env.
        limit: Max entries per feed. Defaults to TEST_MODE_LIMIT.

    Returns:
        List of entry dicts.
    """
    urls = feed_urls or settings.rss_feed_list
    max_items = limit or settings.test_mode_limit
    all_entries: list[dict] = []

    for url in urls:
        if not url:
            continue

        logger.info("Parsing RSS feed: %s", url)

        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.error("Failed to parse %s: %s", url, e)
            continue

        logger.info("Feed '%s' has %d total entries", feed.get("feed", {}).get("title", "unknown"), len(feed.entries))

        for entry in feed.entries[:max_items]:
            all_entries.append(_entry_to_dict(entry))

    logger.info("Total RSS entries fetched: %d", len(all_entries))
    return all_entries


def save_raw_entries(entries: list[dict], output_dir: Path | None = None) -> Path:
    """
    Saves RSS entries to a timestamped JSON file in data/raw/.
    """
    out_dir = output_dir or (Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = out_dir / f"rss_{timestamp}.json"

    filename.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved raw RSS entries to %s", filename)
    return filename