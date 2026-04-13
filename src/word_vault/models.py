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
