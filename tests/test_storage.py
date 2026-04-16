from __future__ import annotations

from pathlib import Path

from word_vault.storage import WordRepository


def build_repo(tmp_path: Path) -> WordRepository:
    return WordRepository(tmp_path / "test.db")


def test_add_get_list_delete(tmp_path: Path) -> None:
    repo = build_repo(tmp_path)

    repo.add_or_replace_word(
        word="apple",
        phonetic="/ˈæp.əl/",
        meaning="A fruit.",
        usage="Common noun.",
        pattern="eat an apple",
        source_sentence="I ate an apple.",
    )

    item = repo.get_word("apple")
    assert item is not None
    assert item.word == "apple"
    assert item.meaning == "A fruit."
    assert item.example_count == 1

    examples = repo.list_examples("apple")
    assert len(examples) == 1
    assert examples[0].sentence == "I ate an apple."
    assert examples[0].seen_count == 1

    items = repo.list_words()
    assert len(items) == 1

    deleted = repo.delete_word("apple")
    assert deleted is True
    assert repo.get_word("apple") is None


def test_duplicate_sentence_increments_seen_count(tmp_path: Path) -> None:
    repo = build_repo(tmp_path)

    repo.add_or_replace_word(
        word="apple",
        phonetic="/ˈæp.əl/",
        meaning="A fruit.",
        usage="Common noun.",
        pattern="eat an apple",
        source_sentence="I ate an apple.",
    )

    added = repo.add_sentence_example(word="apple", sentence="I ate an apple.")
    assert added is False

    examples = repo.list_examples("apple")
    assert len(examples) == 1
    assert examples[0].seen_count == 2


def test_new_sentence_is_stored_without_overwriting_primary(tmp_path: Path) -> None:
    repo = build_repo(tmp_path)

    repo.add_or_replace_word(
        word="apple",
        phonetic="/ˈæp.əl/",
        meaning="A fruit.",
        usage="Common noun.",
        pattern="eat an apple",
        source_sentence="I ate an apple.",
    )

    added = repo.add_sentence_example(word="apple", sentence="Apple pie tastes great.")
    assert added is True

    item = repo.get_word("apple")
    assert item is not None
    assert item.source_sentence == "I ate an apple."
    assert item.example_count == 2

    examples = repo.list_examples("apple")
    assert len(examples) == 2
    assert examples[0].is_primary is True
    assert examples[0].sentence == "I ate an apple."


def test_review_updates_counter(tmp_path: Path) -> None:
    repo = build_repo(tmp_path)

    repo.add_or_replace_word(
        word="banana",
        phonetic="/bəˈnæn.ə/",
        meaning="Another fruit.",
        usage="Common noun.",
        pattern="peel a banana",
        source_sentence="He peeled a banana.",
    )

    candidates = repo.review_candidates(count=1)
    assert len(candidates) == 1
    assert candidates[0].review_count == 0

    repo.mark_reviewed("banana")
    updated = repo.get_word("banana")
    assert updated is not None
    assert updated.review_count == 1
    assert updated.last_reviewed_at is not None
