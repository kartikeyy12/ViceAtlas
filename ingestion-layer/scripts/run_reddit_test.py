"""
run_reddit_test.py — One-off test of the Reddit scraper.

Usage:
    uv run scripts/run_reddit_test.py

What it does:
    1. Pulls posts from configured subreddits (respects TEST_MODE_LIMIT in .env)
    2. Saves raw JSON to data/raw/
    3. Prints a readable sample to terminal so you can eyeball the output
"""

import sys
from pathlib import Path

# Add src/ to Python path so 'import ingestion' works when running scripts directly.
# uv run usually handles this, but this makes it robust for direct execution too.
POJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(POJECT_ROOT / "src"))

from ingestion.scrapers.reddit_scraper import fetch_posts, save_raw_posts
from ingestion.utils.logger import get_logger

logger = get_logger("run_reddit_test")

def main():
    logger.info("=" * 60)
    logger.info("REDDIT SCRAPER TEST")
    logger.info("=" * 60)

    # Fetch in catch-up mode (last N days) with default test limit from .env
    posts = fetch_posts(mode="catchup")

    if not posts:
        logger.warning("No posts fetched. Check your .env SUBREDDITS and Reddit credentials.")
        return
    
    # Save to data/raw/
    file_path = save_raw_posts(posts)
    logger.info("Raw output saved to: %s", file_path)

    # Print readable sample to terminal
    print("\n" + "=" * 60)
    print("SAMPLE OUTPUT (first post):")
    print("=" * 60)

    first = posts[0]
    print(f"\nTitle: {first['title']}")
    print(f"Subreddit: r/{first['subreddit']}")
    print(f"Score: {first['score']} | Upvote ratio: {first['upvote_ratio']}")
    print(f"URL: {first['source_url']}")
    print(f"Comments: {first['num_comments']}")

    body = first['body']
    print(f"\nBody (first 400 chars):")
    print(f"{body[:400]}{'...' if len(body) > 400 else ''}")

    print(f"\n--- Top {len(first['top_comments'])} comments ---")
    for i, c in enumerate(first['top_comments'], 1):
        c_body = c['body'][:200]
        print(f"\n[{i}] {c['author']} (score: {c['score']}):")
        print(f"    {c_body}{'...' if len(c['body']) > 200 else ''}")
        
        if c.get('replies'):
            print(f"    └─ {len(c['replies'])} reply/replies")
            for r in c['replies'][:2]:  # show first 2 replies only in preview
                r_body = r['body'][:120]
                print(f"       └─ {r['author']}: {r_body}{'...' if len(r['body']) > 120 else ''}")

    print("\n" + "=" * 60)
    print(f"Total posts fetched: {len(posts)}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()          