from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class WordEntry:
    word: str
    phonetic: str
    meaning: str
    usage: str
    pattern: str
    source_sentence: str
    created_at: datetime
    updated_at: datetime
    last_reviewed_at: datetime | None
    review_count: int
    ease_factor: float = 2.5
    interval_days: int = 0
    due_at: datetime | None = None
    lapse_count: int = 0
    correct_streak: int = 0
    example_count: int = 0


@dataclass(slots=True)
class WordExample:
    word: str
    sentence: str
    is_primary: bool
    source_type: str
    seen_count: int
    created_at: datetime
    last_seen_at: datetime
