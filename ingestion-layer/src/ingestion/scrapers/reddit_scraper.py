"""
reddit_scraper.py — Pulls posts + top comments from Reddit (PRAW).

WHAT THIS FILE DOES:
    Connects to Reddit's API via PRAW, fetches posts from configured subreddits,
    and returns them as clean Python dictionaries ready for JSON serialization.

TWO MODES:
    1. CATCH-UP MODE (for testing): Pulls last N days of posts.
    2. INCREMENTAL MODE (for cron): Only fetches posts newer than the last cursor.

COMMENT DEPTH:
    - Grabs top N comments per post (default 10).
    - Grabs up to M nested replies per comment (default 5).
    - Edit TOP_COMMENTS and MAX_REPLIES_PER_COMMENT below to change this.

RATE LIMITS / COST:
    - Reddit API: 60 requests/minute for OAuth apps.
    - PRAW handles rate limiting automatically.
    - More comments/replies = more API calls = slower runs.

HOW TO RUN:
    uv run scripts/run_reddit_test.py

HOW TO SWITCH TO GTA 6 LATER:
    Change SUBREDDITS in .env. This file doesn't change.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import praw

from ingestion.config import settings
from ingestion.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# TWEAK THESE NUMBERS WITHOUT DIGGING INTO THE CODE
# =============================================================================
TOP_COMMENTS = 10           # How many top-level comments to grab per post
MAX_REPLIES_PER_COMMENT = 5 # How many nested replies per comment (0 = disable replies)

# Where we store the "last seen" cursor for incremental runs
_CURSOR_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / ".reddit_cursor"


def _get_reddit_client() -> praw.Reddit:
    """Creates an authenticated Reddit client using credentials from .env."""
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )


def _load_cursor() -> datetime | None:
    """Reads the timestamp of the last successful run from disk."""
    if not _CURSOR_FILE.exists():
        return None
    timestamp_str = _CURSOR_FILE.read_text().strip()
    return datetime.fromisoformat(timestamp_str)


def _save_cursor(dt: datetime) -> None:
    """Writes the latest post timestamp to disk for the next incremental run."""
    _CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CURSOR_FILE.write_text(dt.isoformat())


def _comment_to_dict(comment: praw.models.Comment) -> dict[str, Any]:
    """
    Converts a single PRAW Comment (top-level or reply) into a clean dict.
    This is reused for both top-level comments and nested replies.
    """
    return {
        "body": comment.body,
        "author": str(comment.author) if comment.author else "[deleted]",
        "score": comment.score,
        "created_utc": datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
    }


def _fetch_replies(comment: praw.models.Comment, max_replies: int) -> list[dict[str, Any]]:
    """
    Fetches nested replies to a single comment, up to max_replies.
    Returns an empty list if the comment has no replies or if max_replies is 0.
    """
    if max_replies <= 0:
        return []

    # comment.replies is a list of Comment objects (or MoreComments stubs)
    # We filter out stubs and only take real comments
    real_replies = [
        c for c in comment.replies
        if isinstance(c, praw.models.Comment)
    ]

    return [
        _comment_to_dict(reply)
        for reply in real_replies[:max_replies]
    ]


def _post_to_dict(post: praw.models.Submission) -> dict[str, Any]:
    """
    Converts a PRAW Submission object into a plain Python dict.
    Includes top N comments + up to M nested replies per comment.
    """
    # Force PRAW to load real comments instead of "load more" stubs
    post.comments.replace_more(limit=0)

    comments_data: list[dict[str, Any]] = []
    for comment in post.comments[:TOP_COMMENTS]:
        # Skip any remaining stubs (safety check)
        if not isinstance(comment, praw.models.Comment):
            continue

        comment_dict = _comment_to_dict(comment)
        # Attach nested replies
        comment_dict["replies"] = _fetch_replies(comment, MAX_REPLIES_PER_COMMENT)

        comments_data.append(comment_dict)

    return {
        "source": "reddit",
        "source_id": post.id,
        "source_url": f"https://reddit.com{post.permalink}",
        "subreddit": str(post.subreddit),
        "title": post.title,
        "body": post.selftext,
        "author": str(post.author) if post.author else "[deleted]",
        "score": post.score,
        "upvote_ratio": post.upvote_ratio,
        "num_comments": post.num_comments,
        "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
        "top_comments": comments_data,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_posts(
    subreddits: list[str] | None = None,
    mode: str = "catchup",
    limit: int | None = None,
) -> list[dict[str, Any]]:
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
    posts: list[dict[str, Any]] = []

    logger.info(
        "Fetching Reddit posts from: %s | mode=%s | limit=%d | top_comments=%d | max_replies=%d",
        subs, mode, max_items, TOP_COMMENTS, MAX_REPLIES_PER_COMMENT,
    )

    # Calculate cutoff time
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
        for post in subreddit.new(limit=max_items * 3):
            post_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)

            if post_time < cutoff:
                logger.debug("Post %s is before cutoff — stopping this subreddit", post.id)
                break

            posts.append(_post_to_dict(post))

            if len(posts) >= max_items:
                logger.info("Reached limit of %d posts", max_items)
                break

    if posts:
        newest = max(datetime.fromisoformat(p["created_utc"]) for p in posts)
        _save_cursor(newest)
        logger.info("Saved cursor at %s", newest.isoformat())

    logger.info("Total posts fetched: %d", len(posts))
    return posts


def save_raw_posts(posts: list[dict[str, Any]], output_dir: Path | None = None) -> Path:
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