"""
reddit_scraper.py — Pulls posts + top comments from Reddit (PRAW).

WHAT THIS FILE DOES:
    Connects to Reddit's API via PRAW, fetches posts from configured subreddits,
    and returns them as clean Python dictionaries ready for JSON serialization.

TWO MODES:
    1. CATCH-UP MODE (for testing): Pulls last N days of posts.
       Controlled by CATCHUP_DAYS in .env.
    2. INCREMENTAL MODE (for cron): Only fetches posts newer than the last
       stored cursor (a post ID or timestamp saved to disk).

RATE LIMITS / COST:
    - Reddit's API limit: 60 requests/minute for OAuth apps.
    - PRAW handles rate limiting automatically (it sleeps when needed).
    - No cost — Reddit API is free for read-only access.

HOW TO RUN:
    uv run scripts/run_reddit_test.py

HOW TO SWITCH TO GTA 6 LATER:
    Change SUBREDDITS in .env. This file doesn't change.
"""

import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import praw

from ingestion.config import settings
from ingestion.utils.logger import get_logger

logger = get_logger(__name__)

# Where we store the "last seen" cursor for incremental runs
_CURSOR_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / ".reddit_cursor"


def _get_reddit_client() -> praw.Reddit:
    """
    Creates an authenticated Reddit client using credentials from .env.
    PRAW handles OAuth and rate limiting internally.
    """
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )


def _load_cursor() -> datetime | None:
    """
    Reads the timestamp of the last successful run from disk.
    Returns None if no cursor exists (first run).
    """
    if not _CURSOR_FILE.exists():
        return None
    timestamp_str = _CURSOR_FILE.read_text().strip()
    return datetime.fromisoformat(timestamp_str)


def _save_cursor(dt: datetime) -> None:
    """Writes the latest post timestamp to disk for the next incremental run."""
    _CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CURSOR_FILE.write_text(dt.isoformat())


def _post_to_dict(post: praw.models.Submission) -> dict:
    """
    Converts a PRAW Submission object into a plain Python dict.
    This is what gets saved as raw JSON.
    """
    # PRAW lazily loads comments — force fetch top-level ones
    post.comments.replace_more(limit=0)  # remove "load more" stubs
    top_comments = [
        {
            "body": c.body,
            "author": str(c.author) if c.author else "[deleted]",
            "score": c.score,
        }
        for c in post.comments[:5]  # top 5 comments only
    ]

    return {
        "source": "reddit",
        "source_id": post.id,
        "source_url": f"https://reddit.com{post.permalink}",
        "subreddit": str(post.subreddit),
        "title": post.title,
        "body": post.selftext,  # empty for link posts, text for self posts
        "author": str(post.author) if post.author else "[deleted]",
        "score": post.score,
        "upvote_ratio": post.upvote_ratio,
        "num_comments": post.num_comments,
        "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
        "top_comments": top_comments,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_posts(
    subreddits: list[str] | None = None,
    mode: str = "catchup",
    limit: int | None = None,
) -> list[dict]:
    """
    Main entry point. Fetches posts from configured subreddits.

    Args:
        subreddits: Override list of subreddits. Defaults to .env SUBREDDITS.
        mode: "catchup" (last N days) or "incremental" (since last cursor).
        limit: Max posts to fetch. Defaults to TEST_MODE_LIMIT from .env.

    Returns:
        List of post dictionaries ready for JSON serialization.
    """
    client = _get_reddit_client()
    subs = subreddits or settings.subreddit_list
    max_items = limit or settings.test_mode_limit
    posts: list[dict] = []

    logger.info("Fetching Reddit posts from: %s | mode=%s | limit=%d", subs, mode, max_items)

    # Calculate the cutoff time
    if mode == "catchup":
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.catchup_days)
        logger.info("Catch-up mode: fetching posts since %s", cutoff.isoformat())
    else:
        cutoff = _load_cursor()
        if cutoff:
            logger.info("Incremental mode: fetching posts since %s", cutoff.isoformat())
        else:
            logger.info("No cursor found — falling back to catchup mode")
            cutoff = datetime.now(timezone.utc) - timedelta(days=settings.catchup_days)

    for sub_name in subs:
        logger.info("Scanning r/%s", sub_name)
        subreddit = client.subreddit(sub_name)

        # Sort by "new" so we can stop once we hit the cutoff
        for post in subreddit.new(limit=max_items * 3):  # fetch extra to filter by date
            post_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)

            if post_time < cutoff:
                logger.debug("Post %s is before cutoff — stopping this subreddit", post.id)
                break

            posts.append(_post_to_dict(post))

            if len(posts) >= max_items:
                logger.info("Reached limit of %d posts", max_items)
                break

    if posts:
        newest = max(
            datetime.fromisoformat(p["created_utc"]) for p in posts
        )
        _save_cursor(newest)
        logger.info("Saved cursor at %s", newest.isoformat())

    logger.info("Total posts fetched: %d", len(posts))
    return posts


def save_raw_posts(posts: list[dict], output_dir: Path | None = None) -> Path:
    """
    Saves the raw post list to a timestamped JSON file in data/raw/.
    Returns the path to the saved file.
    """
    out_dir = output_dir or (Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = out_dir / f"reddit_{timestamp}.json"

    filename.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved raw posts to %s", filename)
    return filename