from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from word_vault import cli
from word_vault.storage import WordRepository


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_word_info(self, word: str, sentence: str | None = None) -> dict[str, str]:
        self.calls += 1
        return {
            "phonetic": "/test/",
            "meaning": f"Meaning for {word}",
            "usage": "Usage",
            "pattern": "Pattern",
            "example_sentence": f"Example with {word}.",
        }


class FakeSpeaker:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, word: str, phonetic: str, *, voice: str = "en-us") -> bool:
        self.calls.append({"word": word, "phonetic": phonetic, "voice": voice})
        return True


class FakeTextSpeaker:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, text: str, *, voice: str = "en-us") -> bool:
        self.calls.append({"text": text, "voice": voice})
        return True


@pytest.fixture(autouse=True)
def disable_real_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "play_word_audio", lambda word, phonetic, voice="en-us": True)
    monkeypatch.setattr(cli, "play_text_audio", lambda text, voice="en-us": True)


def test_add_show_delete_flow(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    monkeypatch.setattr(cli, "play_word_audio", fake_speaker)

    runner = CliRunner()

    add_result = runner.invoke(cli.app, ["add", "apple"])
    assert add_result.exit_code == 0
    assert "Saved word: apple" in add_result.stdout
    assert "Word: apple" in add_result.stdout
    assert "Phonetic: /test/" in add_result.stdout
    assert "Meaning: Meaning for apple" in add_result.stdout
    assert "Source sentence: Example with apple." in add_result.stdout
    assert "Example count: 1" in add_result.stdout
    assert fake_client.calls == 1
    assert fake_speaker.calls == [{"word": "apple", "phonetic": "/test/", "voice": "en-us"}]

    cached_add_result = runner.invoke(cli.app, ["add", "apple"])
    assert cached_add_result.exit_code == 0
    assert "Word already exists in local vault: apple" in cached_add_result.stdout
    assert fake_client.calls == 1

    refresh_result = runner.invoke(cli.app, ["add", "apple", "--refresh"])
    assert refresh_result.exit_code == 0
    assert "Updated word from DeepSeek: apple" in refresh_result.stdout
    assert "Word: apple" in refresh_result.stdout
    assert fake_client.calls == 2
    assert fake_speaker.calls[-1] == {"word": "apple", "phonetic": "/test/", "voice": "en-us"}

    show_result = runner.invoke(cli.app, ["show", "apple"])
    assert show_result.exit_code == 0
    assert "Word: apple" in show_result.stdout
    assert "Example count: 1" in show_result.stdout
    assert len(fake_speaker.calls) == 2

    speak_result = runner.invoke(cli.app, ["speak", "apple"])
    assert speak_result.exit_code == 0
    assert speak_result.stdout == ""
    assert fake_speaker.calls[-1] == {"word": "apple", "phonetic": "/test/", "voice": "en-us"}

    review_result = runner.invoke(
        cli.app,
        ["review", "--count", "1"],
        input="apple\nA\n\n4\n",
    )
    assert review_result.exit_code == 0
    assert "Phonetic: /test/" in review_result.stdout
    assert "Meaning choices:" in review_result.stdout
    assert "Saved review for apple: final score=4" in review_result.stdout

    delete_result = runner.invoke(cli.app, ["delete", "apple"])
    assert delete_result.exit_code == 0
    assert "Deleted word: apple" in delete_result.stdout


def test_add_existing_word_with_new_sentence_adds_example_without_llm(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "sentences.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    monkeypatch.setattr(cli, "play_word_audio", fake_speaker)
    runner = CliRunner()

    first_add = runner.invoke(cli.app, ["add", "apple"])
    assert first_add.exit_code == 0
    assert fake_client.calls == 1

    second_add = runner.invoke(
        cli.app,
        ["add", "apple", "--sentence", "I use apple in another sentence."],
    )
    assert second_add.exit_code == 0
    assert "Added new sentence example for: apple" in second_add.stdout
    assert "Example count: 2" in second_add.stdout
    assert "I use apple in another sentence." in second_add.stdout
    assert fake_client.calls == 1
    assert fake_speaker.calls[-1] == {"word": "apple", "phonetic": "/test/", "voice": "en-us"}

    duplicate_sentence_add = runner.invoke(
        cli.app,
        ["add", "apple", "--sentence", "I use apple in another sentence."],
    )
    assert duplicate_sentence_add.exit_code == 0
    assert (
        "Sentence already exists for: apple (seen count increased)"
        in duplicate_sentence_add.stdout
    )
    assert "I use apple in another sentence. (seen: 2)" in duplicate_sentence_add.stdout
    assert fake_client.calls == 1
    assert fake_speaker.calls[-1] == {"word": "apple", "phonetic": "/test/", "voice": "en-us"}


def test_audio_can_be_disabled_with_env(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "audio-disabled.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    monkeypatch.setenv("WORD_VAULT_AUDIO_ENABLED", "0")
    fake_client = FakeClient()
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    monkeypatch.setattr(cli, "play_word_audio", fake_speaker)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["add", "apple"])

    assert result.exit_code == 0
    assert fake_speaker.calls == []

    speak_result = runner.invoke(cli.app, ["speak", "apple"])
    assert speak_result.exit_code == 1
    assert "Audio is disabled." in speak_result.stdout

    review_result = runner.invoke(
        cli.app,
        ["review", "--count", "1"],
        input="apple\nA\n\n4\n",
    )
    assert review_result.exit_code == 0
    assert "Audio is disabled. Running IPA-only dictation prompts." in review_result.stdout


def test_show_speaks_only_with_flag(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "show-speak.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    monkeypatch.setattr(cli, "play_word_audio", fake_speaker)
    runner = CliRunner()

    assert runner.invoke(cli.app, ["add", "apple"]).exit_code == 0
    assert len(fake_speaker.calls) == 1

    show_result = runner.invoke(cli.app, ["show", "apple"])
    assert show_result.exit_code == 0
    assert len(fake_speaker.calls) == 1

    show_with_speak = runner.invoke(cli.app, ["show", "apple", "--speak"])
    assert show_with_speak.exit_code == 0
    assert len(fake_speaker.calls) == 2


def test_speak_returns_error_when_playback_fails(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "speak-fail.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    monkeypatch.setattr(cli, "play_word_audio", lambda word, phonetic, voice="en-us": False)
    runner = CliRunner()

    assert runner.invoke(cli.app, ["add", "apple"]).exit_code == 0

    result = runner.invoke(cli.app, ["speak", "apple"])
    assert result.exit_code == 1
    assert "Unable to play audio." in result.stdout


def test_short_option_aliases_work(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "short-options.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    runner = CliRunner()

    add_result = runner.invoke(
        cli.app,
        ["add", "apple", "-s", "I ate an apple after lunch."],
    )
    assert add_result.exit_code == 0
    assert "Saved word: apple" in add_result.stdout
    assert "Source sentence: I ate an apple after lunch." in add_result.stdout

    refresh_result = runner.invoke(cli.app, ["add", "apple", "-r"])
    assert refresh_result.exit_code == 0
    assert "Updated word from DeepSeek: apple" in refresh_result.stdout

    review_result = runner.invoke(
        cli.app,
        ["review", "-c", "1"],
        input="apple\nA\n\n4\n",
    )
    assert review_result.exit_code == 0
    assert "Saved review for apple: final score=4" in review_result.stdout


def test_word_review_wrong_spelling_one_retry(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "word-review-retry.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)

    runner = CliRunner()
    assert runner.invoke(cli.app, ["add", "apple"]).exit_code == 0

    # Wrong first and second spelling attempts should force a low final quality.
    result = runner.invoke(
        cli.app,
        ["review", "--count", "1"],
        input="aple\napal\nA\n\n5\n",
    )

    assert result.exit_code == 0
    assert "Not correct. Try once more." in result.stdout
    assert "Spelling not correct. Correct word: apple" in result.stdout
    assert "Saved review for apple: final score=1" in result.stdout


def test_review_plays_sentence_audio_and_uses_meaning_distractors(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "review-meaning-options.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    fake_text_speaker = FakeTextSpeaker()
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)
    monkeypatch.setattr(cli, "play_text_audio", fake_text_speaker)
    runner = CliRunner()

    assert runner.invoke(cli.app, ["add", "apple"]).exit_code == 0
    assert runner.invoke(cli.app, ["add", "banana"]).exit_code == 0
    assert runner.invoke(cli.app, ["add", "orange"]).exit_code == 0
    assert runner.invoke(cli.app, ["add", "grape"]).exit_code == 0

    # Force apple to be selected for review while keeping other words available as distractors.
    repo = WordRepository(db_path)
    now = datetime.datetime.now(datetime.UTC)
    past_due = (now - datetime.timedelta(days=1)).isoformat()
    future_due = (now + datetime.timedelta(days=10)).isoformat()
    with repo._connect() as conn:
        conn.execute("UPDATE words SET due_at = ? WHERE word = ?", (past_due, "apple"))
        conn.execute("UPDATE words SET due_at = ? WHERE word IN (?, ?, ?)", (future_due, "banana", "orange", "grape"))
        conn.commit()

    result = runner.invoke(
        cli.app,
        ["review", "--count", "1"],
        input="apple\nA\n\n5\n",
    )

    assert result.exit_code == 0
    assert "Meaning choices:" in result.stdout
    assert "Meaning for banana" in result.stdout
    assert "Meaning for orange" in result.stdout
    assert "Meaning for grape" in result.stdout
    assert "Example with apple." in result.stdout
    assert fake_text_speaker.calls == [{"text": "Example with apple.", "voice": "en-us"}]


def test_show_not_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(tmp_path / "empty.db"))
    runner = CliRunner()

    result = runner.invoke(cli.app, ["show", "missing"])
    assert result.exit_code == 1


def test_list_supports_wildcard_pattern(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "list.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    fake_client = FakeClient()
    runner = CliRunner()

    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: fake_client)

    assert runner.invoke(cli.app, ["add", "apple"]).exit_code == 0
    assert runner.invoke(cli.app, ["add", "application"]).exit_code == 0
    assert runner.invoke(cli.app, ["add", "banana"]).exit_code == 0

    result = runner.invoke(cli.app, ["list", "app*"])

    assert result.exit_code == 0
    assert "- apple /test/:" in result.stdout
    assert "- application /test/:" in result.stdout
    assert "- banana /test/:" not in result.stdout

    second_result = runner.invoke(cli.app, ["list", "b*"])

    assert second_result.exit_code == 0
    assert "- banana /test/:" in second_result.stdout
    assert "- apple /test/:" not in second_result.stdout


def test_root_no_args_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, [])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "Word Vault CLI" in result.stdout


def test_root_short_h_matches_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ["-h"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "Word Vault CLI" in result.stdout
