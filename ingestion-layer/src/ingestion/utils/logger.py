"""
logger.py — Central logging setup.

WHAT THIS FILE DOES:
    Provides a single function `get_logger(name)` that returns a logger configured
    with a consistent format across the entire ingestion layer.

WHY IT'S STRUCTURED THIS WAY:
    - Every scraper, extractor, and deduplicator uses the same format.
    - You can change the format in ONE place and it updates everywhere.
    - Logs include timestamps, module name, and log level so you can grep/filter
      when reading terminal output.

HOW TO USE IT:
    from ingestion.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Starting Reddit scraper...")
    logger.warning("Rate limit approaching...")
    logger.error("Failed to fetch post: %s", post_id)
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Create or retrieve a logger with a consistent console format.

    Args:
        name: Usually __name__ from the calling module. This becomes the logger's
              identity, so you know which file produced each log line.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Only add handlers if this logger doesn't already have them.
    # Prevents duplicate log lines if get_logger is called multiple times.
    if not logger.handlers:
        # Console handler — prints to stdout (what you see in VS Code terminal)
        handler = logging.StreamHandler(sys.stdout)

        # Format: 2026-07-13 21:02:15 | ingestion.scrapers.reddit_scraper | INFO | message
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(logging.INFO)  # Change to DEBUG for more verbosity

    return logger