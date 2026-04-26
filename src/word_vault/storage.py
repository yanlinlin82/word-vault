from __future__ import annotations

import datetime
import random
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
    review_count INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    due_at TEXT,
    lapse_count INTEGER NOT NULL DEFAULT 0,
    correct_streak INTEGER NOT NULL DEFAULT 0
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
            self._migrate_words_schema(conn)
            self._backfill_examples_from_words(conn)
            conn.commit()

    def _migrate_words_schema(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(words)").fetchall()
        }
        migrations: list[tuple[str, str]] = [
            ("ease_factor", "ALTER TABLE words ADD COLUMN ease_factor REAL NOT NULL DEFAULT 2.5"),
            (
                "interval_days",
                "ALTER TABLE words ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 0",
            ),
            ("due_at", "ALTER TABLE words ADD COLUMN due_at TEXT"),
            (
                "lapse_count",
                "ALTER TABLE words ADD COLUMN lapse_count INTEGER NOT NULL DEFAULT 0",
            ),
            (
                "correct_streak",
                "ALTER TABLE words ADD COLUMN correct_streak INTEGER NOT NULL DEFAULT 0",
            ),
        ]
        for column, sql in migrations:
            if column not in columns:
                conn.execute(sql)

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
                    created_at, updated_at, last_reviewed_at, review_count,
                    ease_factor, interval_days, due_at, lapse_count, correct_streak
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, 2.5, 0, NULL, 0, 0)
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
                    (
                        SELECT COUNT(*)
                        FROM word_examples we
                        WHERE we.word = w.word
                    ) AS example_count
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
                        (
                            SELECT COUNT(*)
                            FROM word_examples we
                            WHERE we.word = w.word
                        ) AS example_count
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
                        (
                            SELECT COUNT(*)
                            FROM word_examples we
                            WHERE we.word = w.word
                        ) AS example_count
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
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._connect() as conn:
            due_rows = conn.execute(
                """
                SELECT *
                FROM words
                WHERE due_at IS NULL OR due_at <= ?
                """,
                (now,),
            ).fetchall()
            future_rows = conn.execute(
                """
                SELECT *
                FROM words
                WHERE due_at > ?
                """,
                (now,),
            ).fetchall()

        random.shuffle(due_rows)
        random.shuffle(future_rows)
        rows = [*due_rows, *future_rows][:count]
        return [self._row_to_entry(row) for row in rows]

    def review_meaning_options(self, word: str, option_count: int = 4) -> list[str]:
        target = self.get_word(word)
        if target is None:
            return []

        distractor_limit = max(0, option_count - 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT meaning
                FROM words
                WHERE word != ? AND meaning != ?
                ORDER BY meaning ASC
                LIMIT ?
                """,
                (word.lower(), target.meaning, distractor_limit),
            ).fetchall()

        return [target.meaning, *[row["meaning"] for row in rows]]

    def mark_reviewed(self, word: str) -> None:
        self.record_review_result(word, quality=4)

    def record_review_result(self, word: str, quality: int) -> None:
        bounded_quality = max(0, min(5, quality))
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT ease_factor, interval_days, lapse_count, correct_streak
                FROM words
                WHERE word = ?
                """,
                (word.lower(),),
            ).fetchone()
            if row is None:
                return

            next_ease_factor, next_interval_days, next_lapse_count, next_correct_streak = (
                self._compute_next_schedule(
                    ease_factor=float(row["ease_factor"]),
                    interval_days=int(row["interval_days"]),
                    lapse_count=int(row["lapse_count"]),
                    correct_streak=int(row["correct_streak"]),
                    quality=bounded_quality,
                )
            )
            due_at = (
                datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(days=next_interval_days)
            ).isoformat()
            conn.execute(
                """
                UPDATE words
                SET
                    last_reviewed_at = ?,
                    review_count = review_count + 1,
                    ease_factor = ?,
                    interval_days = ?,
                    due_at = ?,
                    lapse_count = ?,
                    correct_streak = ?
                WHERE word = ?
                """,
                (
                    now,
                    next_ease_factor,
                    next_interval_days,
                    due_at,
                    next_lapse_count,
                    next_correct_streak,
                    word.lower(),
                ),
            )
            conn.commit()

    @staticmethod
    def _compute_next_schedule(
        *,
        ease_factor: float,
        interval_days: int,
        lapse_count: int,
        correct_streak: int,
        quality: int,
    ) -> tuple[float, int, int, int]:
        quality_gap = 5 - quality
        next_ease_factor = ease_factor + (
            0.1 - quality_gap * (0.08 + quality_gap * 0.02)
        )
        next_ease_factor = max(1.3, round(next_ease_factor, 2))

        if quality < 3:
            return next_ease_factor, 1, lapse_count + 1, 0

        next_correct_streak = correct_streak + 1
        if next_correct_streak == 1:
            next_interval_days = 1
        elif next_correct_streak == 2:
            next_interval_days = 6
        else:
            next_interval_days = max(1, round(interval_days * next_ease_factor))
        return next_ease_factor, next_interval_days, lapse_count, next_correct_streak

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
            ease_factor=float(row["ease_factor"]) if "ease_factor" in row.keys() else 2.5,
            interval_days=int(row["interval_days"]) if "interval_days" in row.keys() else 0,
            due_at=(
                datetime.datetime.fromisoformat(row["due_at"])
                if "due_at" in row.keys() and row["due_at"]
                else None
            ),
            lapse_count=int(row["lapse_count"]) if "lapse_count" in row.keys() else 0,
            correct_streak=(
                int(row["correct_streak"]) if "correct_streak" in row.keys() else 0
            ),
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
