"""
schemas.py — The extraction output contract.

HOW TO CHANGE THE SCHEMA LATER:
1. Edit this file (add/remove fields or add new entity classes).
2. Update ingestion/extraction/prompts.py so the LLM knows about the new fields.
3. Update ingestion/extraction/ai_extractor.py if the parsing logic needs to change.
4. When Phase 1 starts, mirror this schema into storage/mongodb/schema_definitions/
   and backend/src/backend/models/ so the DB and API stay in sync.

If you want to extract a totally different entity type (e.g., "Character" or "Vehicle"),
just add a new Pydantic class below that inherits from BaseExtractedItem, and add it
to the ExtractedItem union at the bottom.
"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    """Where the raw data came from. Add new sources here if you expand beyond Reddit/YouTube/RSS."""
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    RSS = "rss"


class ReviewStatus(str, Enum):
    """Moderation pipeline status. Scraped content starts as PENDING."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BaseExtractedItem(BaseModel):
    """
    Shared fields across every extracted entity.
    Every Mission, Reward, and PatchNote inherits these automatically.
    """
    source: SourceType = Field(..., description="Origin platform")
    source_url: HttpUrl = Field(..., description="Direct link to original post/video/article")
    source_id: Optional[str] = Field(
        None, description="Platform-specific ID (Reddit post ID, YouTube video ID, etc.)"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the LLM extracted this"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM confidence score (0.0–1.0)"
    )
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING, description="Current moderation status"
    )
    raw_text_hash: Optional[str] = Field(
        None, description="SHA-256 hash of raw input text — used for dedup tracing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source": "reddit",
                "source_url": "https://reddit.com/r/GTA5/comments/abc123",
                "extracted_at": "2026-07-13T21:02:00Z",
                "confidence": 0.92,
                "review_status": "pending",
            }
        }


class Mission(BaseExtractedItem):
    """A structured game mission extracted from raw text."""
    entity_type: Literal["mission"] = "mission"
    title: str = Field(..., description="Mission name (e.g., 'The Jewel Store Job')")
    description: str = Field(..., description="What the mission involves")
    steps: list[str] = Field(default_factory=list, description="Ordered completion steps")
    prerequisites: list[str] = Field(
        default_factory=list, description="Requirements before starting (missions, items, etc.)"
    )
    rewards: list[str] = Field(
        default_factory=list, description="Names/IDs of rewards granted"
    )
    difficulty: Optional[str] = Field(
        None, description="Difficulty mentioned by the source (e.g., 'hard', 'easy')"
    )
    location: Optional[str] = Field(
        None, description="In-game starting location or area"
    )
    game_version: Optional[str] = Field(
        None, description="Which game this applies to ('GTA 5' or 'GTA VI')"
    )


class Reward(BaseExtractedItem):
    """A reward, unlock, or collectible."""
    entity_type: Literal["reward"] = "reward"
    name: str = Field(..., description="Reward name")
    reward_type: str = Field(
        ..., description="Category: weapon, vehicle, cash, clothing, property, etc."
    )
    description: str = Field(..., description="What it is and how it's obtained")
    map_location: Optional[str] = Field(
        None, description="Where to find/claim it on the map"
    )
    associated_mission: Optional[str] = Field(
        None, description="Mission name that grants this reward"
    )
    value: Optional[str] = Field(
        None, description="Cash value or rarity if mentioned"
    )


class PatchNote(BaseExtractedItem):
    """An official patch, update, or newswire entry."""
    entity_type: Literal["patch_note"] = "patch_note"
    title: str = Field(..., description="Headline or patch title")
    version: Optional[str] = Field(None, description="Game version number (e.g., '1.68')")
    date: Optional[datetime] = Field(None, description="Patch release date")
    summary: str = Field(..., description="What changed — fixes, additions, balances")
    category: Optional[str] = Field(
        None, description="Type: bugfix, content, balance, event, etc."
    )


# Union type used by the AI extractor and deduplicator.
# If you add a new entity class (e.g., class Vehicle(BaseExtractedItem)),
# append it here so the pipeline knows about it.
ExtractedItem = Mission | Reward | PatchNote