"""
run_youtube_test.py — One-off test of the YouTube transcript monitor.

Usage:
    uv run scripts/run_youtube_test.py [VIDEO_ID_OR_URL]

What it does:
    1. Fetches transcript for a video (from .env or command line arg)
    2. Applies vocabulary correction
    3. Saves raw + corrected JSON to data/raw/
    4. Prints a readable sample to terminal
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ingestion.scrapers.youtube_monitor import fetch_transcript, save_raw_transcript
from ingestion.utils.logger import get_logger
from ingestion.config import settings

logger = get_logger("run_youtube_test")

def main():
    parser = argparse.ArgumentParser(description="Test YouTube transcript fetching.")
    parser.add_argument(
        "video",
        nargs="?",
        default=None,
        help="YouTube video ID or URL (optional, falls back to .env YOUTUBE_SOURCES)",
    )
    args = parser.parse_args()

    # Determine video source: CLI arg > .env > fallback
    if args.video:
        sources = [args.video]
        logger.info("using video from command line: %s", args.video)
    elif settings.youtube_source_list:
        sources = settings.youtube_source_list
        logger.info("using video from .env YOUTUBE_SOURCES: %s", sources)
    else:
        logger.error(
            "No video source provided.\n"
            "  Option 1: Add YOUTUBE_SOURCES to your .env\n"
            "  Option 2: Pass a video ID/URL as argument:\n"
            "    uv run scripts/run_youtube_test.py dQw4w9WgXcQ"
        )
        return
    
    logger.info("=" * 60)
    logger.info("YOUTUBE TRANSCRIPT TEST")
    logger.info("=" * 60)

    # Fetch transcript for the first source only (test mode)
    transcript = fetch_transcript(sources[0], correct=True)

    if not transcript:
        logger.warning("No transcript fetched. The video may have captions disabled.")
        return
    
    # Save
    file_path = save_raw_transcript([transcript])
    logger.info("Raw output saved to: %s", file_path)

    # Print sample
    print("\n" + "=" * 60)
    print("SAMPLE OUTPUT:")
    print("=" * 60)
    print(f"\nVideo ID: {transcript['source_id']}")
    print(f"URL: {transcript['source_url']}")
    print(f"Language: {transcript['language']}")

    raw = transcript['transcript_raw']
    corr = transcript['transcript_corrected']

    print(f"\n--- RAW transcript (first 400 chars) ---")
    print(f"{raw[:400]}{'...' if len(raw) > 400 else ''}")

    print(f"\n--- CORRECTED transcript (first 400 chars) ---")
    print(f"{corr[:400]}{'...' if len(corr) > 400 else ''}")

    # Show any vocabulary corrections that were applied
    if raw != corr:
        print(f"\n--- Vocabulary corrections applied ---")
        # Simple diff: find words that changed
        raw_words = set(raw.lower().split())
        corr_words = set(corr.lower().split())
        changed = corr_words - raw_words
        if changed:
            print(f"Words corrected/added: {', '.join(list(changed)[:10])}")

    print("\n" + "=" * 60)
    print(f"Total transcript length: {len(corr)} chars")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()