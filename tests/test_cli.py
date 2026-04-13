from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from word_vault import cli


class FakeClient:
    def fetch_word_info(self, word: str, sentence: str | None = None) -> dict[str, str]:
        return {
            "phonetic": "/test/",
            "meaning": f"Meaning for {word}",
            "usage": "Usage",
            "pattern": "Pattern",
            "example_sentence": f"Example with {word}.",
        }


def test_add_show_delete_flow(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(db_path))
    monkeypatch.setattr(cli, "get_deepseek_client", lambda settings: FakeClient())

    runner = CliRunner()

    add_result = runner.invoke(cli.app, ["add", "apple"])
    assert add_result.exit_code == 0
    assert "Saved word: apple" in add_result.stdout

    show_result = runner.invoke(cli.app, ["show", "apple"])
    assert show_result.exit_code == 0
    assert "Word: apple" in show_result.stdout

    review_result = runner.invoke(cli.app, ["review", "--count", "1"])
    assert review_result.exit_code == 0
    assert "[apple]" in review_result.stdout

    delete_result = runner.invoke(cli.app, ["delete", "apple"])
    assert delete_result.exit_code == 0
    assert "Deleted word: apple" in delete_result.stdout


def test_show_not_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WORD_VAULT_DB_PATH", str(tmp_path / "empty.db"))
    runner = CliRunner()

    result = runner.invoke(cli.app, ["show", "missing"])
    assert result.exit_code == 1
