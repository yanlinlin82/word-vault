from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

from .models import WordEntry, WordExample

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

CREATE TABLE IF NOT EXISTS word_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    sentence TEXT NOT NULL,
    sentence_key TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(word, sentence_key),
    FOREIGN KEY(word) REFERENCES words(word) ON DELETE CASCADE
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
            conn.executescript(SCHEMA_SQL)
            self._backfill_examples_from_words(conn)
            conn.commit()

    def _backfill_examples_from_words(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT w.word, w.source_sentence, w.created_at, w.updated_at
            FROM words w
            LEFT JOIN word_examples we ON we.word = w.word
            WHERE we.id IS NULL
            """
        ).fetchall()
        for row in rows:
            sentence = row["source_sentence"]
            sentence_key = self._normalize_sentence_key(sentence)
            created_at = row["created_at"]
            last_seen_at = row["updated_at"]
            conn.execute(
                """
                INSERT INTO word_examples (
                    word, sentence, sentence_key, is_primary, source_type,
                    seen_count, created_at, last_seen_at
                ) VALUES (?, ?, ?, 1, 'legacy', 1, ?, ?)
                """,
                (row["word"], sentence, sentence_key, created_at, last_seen_at),
            )

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
        normalized_word = word.lower()
        existing = self.get_word(normalized_word)
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
                    updated_at=excluded.updated_at
                """,
                (normalized_word, phonetic, meaning, usage, pattern, source_sentence, now, now),
            )
            self._add_or_touch_example(
                conn,
                word=normalized_word,
                sentence=source_sentence,
                source_type="llm",
                set_primary=existing is None,
            )
            conn.commit()

    def add_sentence_example(
        self,
        *,
        word: str,
        sentence: str,
        source_type: str = "user",
        set_primary: bool = False,
    ) -> bool:
        normalized_word = word.lower()
        with self._connect() as conn:
            changed = self._add_or_touch_example(
                conn,
                word=normalized_word,
                sentence=sentence,
                source_type=source_type,
                set_primary=set_primary,
            )
            self._sync_primary_source_sentence(conn, normalized_word)
            conn.commit()
        return changed

    def _add_or_touch_example(
        self,
        conn: sqlite3.Connection,
        *,
        word: str,
        sentence: str,
        source_type: str,
        set_primary: bool,
    ) -> bool:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        sentence_key = self._normalize_sentence_key(sentence)
        existing_row = conn.execute(
            """
            SELECT id
            FROM word_examples
            WHERE word = ? AND sentence_key = ?
            """,
            (word, sentence_key),
        ).fetchone()

        has_primary = (
            conn.execute(
                "SELECT 1 FROM word_examples WHERE word = ? AND is_primary = 1 LIMIT 1",
                (word,),
            ).fetchone()
            is not None
        )
        should_set_primary = set_primary or not has_primary

        if existing_row:
            conn.execute(
                """
                UPDATE word_examples
                SET
                    sentence = ?,
                    source_type = ?,
                    seen_count = seen_count + 1,
                    last_seen_at = ?,
                    is_primary = CASE WHEN ? THEN 1 ELSE is_primary END
                WHERE id = ?
                """,
                (sentence, source_type, now, 1 if should_set_primary else 0, existing_row["id"]),
            )
            if should_set_primary:
                conn.execute(
                    """
                    UPDATE word_examples
                    SET is_primary = CASE WHEN id = ? THEN 1 ELSE 0 END
                    WHERE word = ?
                    """,
                    (existing_row["id"], word),
                )
            return False

        conn.execute(
            """
            INSERT INTO word_examples (
                word, sentence, sentence_key, is_primary, source_type,
                seen_count, created_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (word, sentence, sentence_key, 1 if should_set_primary else 0, source_type, now, now),
        )
        self._sync_primary_source_sentence(conn, word)
        return True

    def _sync_primary_source_sentence(self, conn: sqlite3.Connection, word: str) -> None:
        primary_row = conn.execute(
            """
            SELECT sentence
            FROM word_examples
            WHERE word = ? AND is_primary = 1
            LIMIT 1
            """,
            (word,),
        ).fetchone()
        if primary_row is None:
            fallback_row = conn.execute(
                """
                SELECT sentence
                FROM word_examples
                WHERE word = ?
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (word,),
            ).fetchone()
            if fallback_row is None:
                return
            conn.execute(
                """
                UPDATE word_examples
                SET is_primary = CASE WHEN id = (
                    SELECT id
                    FROM word_examples
                    WHERE word = ?
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                ) THEN 1 ELSE 0 END
                WHERE word = ?
                """,
                (word, word),
            )
            primary_sentence = fallback_row["sentence"]
        else:
            primary_sentence = primary_row["sentence"]

        conn.execute(
            "UPDATE words SET source_sentence = ? WHERE word = ?",
            (primary_sentence, word),
        )

    def get_word(self, word: str) -> WordEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    w.*,
                    (SELECT COUNT(*) FROM word_examples we WHERE we.word = w.word) AS example_count
                FROM words w
                WHERE w.word = ?
                """,
                (word.lower(),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_examples(self, word: str) -> list[WordExample]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM word_examples
                WHERE word = ?
                ORDER BY is_primary DESC, created_at ASC, id ASC
                """,
                (word.lower(),),
            ).fetchall()
        return [self._row_to_example(row) for row in rows]

    def list_words(self, pattern: str | None = None) -> list[WordEntry]:
        with self._connect() as conn:
            if pattern:
                rows = conn.execute(
                    """
                    SELECT
                        w.*,
                        (SELECT COUNT(*) FROM word_examples we WHERE we.word = w.word) AS example_count
                    FROM words w
                    WHERE w.word GLOB ?
                    ORDER BY w.word ASC
                    """,
                    (pattern.lower(),),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        w.*,
                        (SELECT COUNT(*) FROM word_examples we WHERE we.word = w.word) AS example_count
                    FROM words w
                    ORDER BY w.word ASC
                    """
                ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def delete_word(self, word: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM word_examples WHERE word = ?", (word.lower(),))
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
            example_count=row["example_count"] if "example_count" in row.keys() else 0,
        )

    @staticmethod
    def _row_to_example(row: sqlite3.Row) -> WordExample:
        return WordExample(
            word=row["word"],
            sentence=row["sentence"],
            is_primary=bool(row["is_primary"]),
            source_type=row["source_type"],
            seen_count=row["seen_count"],
            created_at=datetime.datetime.fromisoformat(row["created_at"]),
            last_seen_at=datetime.datetime.fromisoformat(row["last_seen_at"]),
        )

    @staticmethod
    def _normalize_sentence_key(sentence: str) -> str:
        return " ".join(sentence.split()).lower()
