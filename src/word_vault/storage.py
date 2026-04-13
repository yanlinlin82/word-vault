from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

from .models import WordEntry

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS words (
    word TEXT PRIMARY KEY,
    phonetic TEXT NOT NULL,
    meaning TEXT NOT NULL,
    usage TEXT NOT NULL,
    pattern TEXT NOT NULL,
    source_sentence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_reviewed_at TEXT,
    review_count INTEGER NOT NULL DEFAULT 0
);
"""


class WordRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()

    def ensure_schema(self) -> None:
        self._init_db()

    def add_or_replace_word(
        self,
        *,
        word: str,
        phonetic: str,
        meaning: str,
        usage: str,
        pattern: str,
        source_sentence: str,
    ) -> None:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO words (
                    word, phonetic, meaning, usage, pattern, source_sentence,
                    created_at, updated_at, last_reviewed_at, review_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)
                ON CONFLICT(word) DO UPDATE SET
                    phonetic=excluded.phonetic,
                    meaning=excluded.meaning,
                    usage=excluded.usage,
                    pattern=excluded.pattern,
                    source_sentence=excluded.source_sentence,
                    updated_at=excluded.updated_at
                """,
                (word.lower(), phonetic, meaning, usage, pattern, source_sentence, now, now),
            )
            conn.commit()

    def get_word(self, word: str) -> WordEntry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM words WHERE word = ?", (word.lower(),)).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_words(self) -> list[WordEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM words ORDER BY word ASC").fetchall()
        return [self._row_to_entry(row) for row in rows]

    def delete_word(self, word: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM words WHERE word = ?", (word.lower(),))
            conn.commit()
            return cur.rowcount > 0

    def review_candidates(self, count: int) -> list[WordEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM words
                ORDER BY
                    CASE WHEN last_reviewed_at IS NULL THEN 0 ELSE 1 END,
                    last_reviewed_at ASC,
                    review_count ASC,
                    updated_at ASC
                LIMIT ?
                """,
                (count,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def mark_reviewed(self, word: str) -> None:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE words
                SET last_reviewed_at = ?, review_count = review_count + 1
                WHERE word = ?
                """,
                (now, word.lower()),
            )
            conn.commit()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> WordEntry:
        return WordEntry(
            word=row["word"],
            phonetic=row["phonetic"],
            meaning=row["meaning"],
            usage=row["usage"],
            pattern=row["pattern"],
            source_sentence=row["source_sentence"],
            created_at=datetime.datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.datetime.fromisoformat(row["updated_at"]),
            last_reviewed_at=(
                datetime.datetime.fromisoformat(row["last_reviewed_at"])
                if row["last_reviewed_at"]
                else None
            ),
            review_count=row["review_count"],
        )
