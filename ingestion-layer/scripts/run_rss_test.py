#!/usr/bin/env python3
"""
run_rss_test.py — One-off test of the RSS parser.

Usage:
    uv run scripts/run_rss_test.py

What it does:
    1. Parses configured RSS feeds (from .env RSS_FEEDS)
    2. Saves raw JSON to data/raw/
    3. Prints a readable sample to terminal
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ingestion.scrapers.rss_parser import fetch_feeds, save_raw_entries
from ingestion.utils.logger import get_logger

logger = get_logger("run_rss_test")


def main():
    logger.info("=" * 60)
    logger.info("RSS PARSER TEST")
    logger.info("=" * 60)

    # Fetch feeds
    entries = fetch_feeds()

    if not entries:
        logger.warning("No entries fetched. Check your .env RSS_FEEDS setting.")
        return

    # Save
    file_path = save_raw_entries(entries)
    logger.info("Raw output saved to: %s", file_path)

    # Print sample
    print("\n" + "=" * 60)
    print("SAMPLE OUTPUT (first 3 entries):")
    print("=" * 60)

    for i, entry in enumerate(entries[:3], 1):
        print(f"\n--- Entry {i} ---")
        print(f"Title: {entry['title']}")
        print(f"Published: {entry['published'] or 'N/A'}")
        print(f"URL: {entry['source_url']}")
        print(f"Author: {entry['author'] or 'N/A'}")

        body = entry['body'] or entry['summary']
        print(f"Body (first 350 chars):")
        print(f"{body[:350]}{'...' if len(body) > 350 else ''}")

    print("\n" + "=" * 60)
    print(f"Total entries fetched: {len(entries)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()