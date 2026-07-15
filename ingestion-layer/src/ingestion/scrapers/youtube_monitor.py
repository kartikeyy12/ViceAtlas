"""
youtube_monitor.py — Pulls YouTube video transcripts and corrects game-term mistranscriptions.

WHAT THIS FILE DOES:
    Given a list of YouTube video IDs or channel IDs, fetches auto-generated
    captions via youtube-transcript-api, then runs a vocabulary-correction pass
    to fix common OCR/caption errors (e.g., "Lazlow" → "Lazlow", "Deluxo" → "Deluxo").

VOCABULARY LIST:
    Stored as a plain Python dict in this file (see _GTA5_VOCAB below).
    To add new terms, just edit the dict — no code changes needed.

RATE LIMITS / COST:
    - youtube-transcript-api is free and unauthenticated.
    - No API key required for transcripts (but YouTube Data API v3 needs one for metadata).
    - Be respectful: don't hammer thousands of videos.

HOW TO RUN:
    uv run scripts/run_youtube_test.py

HOW TO SWITCH TO GTA 6 LATER:
    Change YOUTUBE_SOURCES in .env. Update _GTA5_VOCAB to _GTA6_VOCAB when you have terms.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from ingestion.config import settings
from ingestion.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# EDIT THIS DICT TO ADD/REMOVE GAME TERMS — NO CODE CHANGES NEEDED
# Keys = what the caption likely says (wrong). Values = what it should be (correct).
# =============================================================================
_GTA5_VOCAB: dict[str, str] = {
    # Common auto-caption mangling of GTA 5 terms
    "lazlo": "Lazlow",
    "lazlow": "Lazlow",
    "deluxo": "Deluxo",
    "oppressor": "Oppressor",
    "oppresser": "Oppressor",
    "bati": "Bati",
    "baddi": "Bati",
    "karuma": "Kuruma",
    "kuruma": "Kuruma",
    "zancudo": "Zancudo",
    "sandy shores": "Sandy Shores",
    "los santos": "Los Santos",
    "vinewood": "Vinewood",
    "trevor": "Trevor",
    "michael": "Michael",
    "franklin": "Franklin",
    "lamar": "Lamar",
    "lester": "Lester",
    "fleeca": "Fleeca",
    "pacific standard": "Pacific Standard",
    "prison break": "Prison Break",
    "humane labs": "Humane Labs",
    "series a": "Series A",
}


def _correct_transcript(text: str, vocab: dict[str, str] | None = None) -> str:
    """
    Post-processing step: replaces common mistranscriptions with correct game terms.

    Uses word-boundary regex matching so "bati" doesn't match "bathtub".
    Case-insensitive search, preserves original casing of replacement.

    Args:
        text: Raw transcript text from YouTube.
        vocab: Override vocabulary dict. Defaults to _GTA5_VOCAB.

    Returns:
        Corrected transcript text.
    """
    vocab = vocab or _GTA5_VOCAB
    corrected = text

    for wrong, right in vocab.items():
        # \b = word boundary, so "bati" matches "bati" but not "bathtub"
        # re.IGNORECASE = case-insensitive
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        corrected = pattern.sub(right, corrected)

    return corrected


def _video_id_from_url(url: str) -> str:
    """
    Extracts an 11-character YouTube video ID from various URL formats.
    Supports: youtube.com/watch?v=..., youtu.be/..., youtube.com/shorts/...
    """
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",  # watch?v= and shorts/
        r"youtu\.be\/([0-9A-Za-z_-]{11})",   # youtu.be/
    ]
    for pat in patterns:
        match = re.search(pat, url)
        if match:
            return match.group(1)
    # If it's already just an ID, return as-is if valid length
    if len(url) == 11:
        return url
    raise ValueError(f"Could not extract video ID from: {url}")


def fetch_transcript(video_id: str, correct: bool = True) -> dict | None:
    """
    Fetches transcript for a single video and optionally applies vocabulary correction.

    Args:
        video_id: 11-char YouTube ID or full URL.
        correct: Whether to run the vocabulary post-processor.

    Returns:
        Dict with metadata and transcript text, or None if no transcript available.
    """
    vid = _video_id_from_url(video_id) if "youtube" in video_id or "youtu.be" in video_id else video_id

    logger.info("Fetching transcript for video %s", vid)

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(vid)
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.warning("No transcript for %s: %s", vid, e)
        return None
    except Exception as e:
        logger.error("Failed to fetch transcript for %s: %s", vid, e)
        return None

    # Concatenate all transcript segments with timestamps
    raw_text = " ".join(segment["text"] for segment in transcript_list)
    full_text = _correct_transcript(raw_text) if correct else raw_text

    return {
        "source": "youtube",
        "source_id": vid,
        "source_url": f"https://youtube.com/watch?v={vid}",
        "title": None,  # would need YouTube Data API v3 for title
        "transcript_raw": raw_text,
        "transcript_corrected": full_text,
        "language": transcript_list[0].get("language", "unknown") if transcript_list else "unknown",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_transcripts(
    sources: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Fetches transcripts for multiple videos.

    Args:
        sources: List of video IDs or URLs. Defaults to YOUTUBE_SOURCES from .env.
        limit: Max videos to process. Defaults to TEST_MODE_LIMIT.

    Returns:
        List of transcript dicts (None entries filtered out).
    """
    srcs = sources or settings.youtube_source_list
    max_items = limit or settings.test_mode_limit

    results: list[dict] = []
    for src in srcs[:max_items]:
        result = fetch_transcript(src)
        if result:
            results.append(result)

    logger.info("Fetched %d/%d transcripts successfully", len(results), len(srcs[:max_items]))
    return results


def save_raw_transcripts(transcripts: list[dict], output_dir: Path | None = None) -> Path:
    """
    Saves transcripts to a timestamped JSON file in data/raw/.
    """
    out_dir = output_dir or (Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = out_dir / f"youtube_{timestamp}.json"

    filename.write_text(json.dumps(transcripts, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved raw transcripts to %s", filename)
    return filename