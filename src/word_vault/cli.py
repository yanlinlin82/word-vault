from __future__ import annotations

from typing import Annotated

import typer

from .config import Settings, get_settings
from .services.llm_client import DeepSeekClient
from .storage import WordRepository

app = typer.Typer(help="Word Vault CLI")


def get_repo(settings: Settings) -> WordRepository:
    return WordRepository(settings.db_path)


def get_deepseek_client(settings: Settings) -> DeepSeekClient:
    return DeepSeekClient(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )


@app.command("init-db")
def init_db() -> None:
    """Initialize local SQLite schema."""
    settings = get_settings()
    repo = get_repo(settings)
    repo.ensure_schema()
    typer.echo(f"Database ready: {settings.db_path}")


@app.command()
def add(
    word: str,
    sentence: Annotated[str | None, typer.Option(help="Optional context sentence")] = None,
) -> None:
    """Add or update a word by querying DeepSeek."""
    settings = get_settings()
    repo = get_repo(settings)
    client = get_deepseek_client(settings)

    payload = client.fetch_word_info(word=word, sentence=sentence)
    source_sentence = sentence or payload["example_sentence"]

    repo.add_or_replace_word(
        word=word,
        phonetic=payload["phonetic"],
        meaning=payload["meaning"],
        usage=payload["usage"],
        pattern=payload["pattern"],
        source_sentence=source_sentence,
    )
    typer.echo(f"Saved word: {word.lower()}")


@app.command()
def show(word: str) -> None:
    """Show details of one word."""
    settings = get_settings()
    repo = get_repo(settings)
    item = repo.get_word(word)

    if item is None:
        raise typer.Exit(code=1)

    typer.echo(f"Word: {item.word}")
    typer.echo(f"Phonetic: {item.phonetic}")
    typer.echo(f"Meaning: {item.meaning}")
    typer.echo(f"Usage: {item.usage}")
    typer.echo(f"Pattern: {item.pattern}")
    typer.echo(f"Source sentence: {item.source_sentence}")
    typer.echo(f"Review count: {item.review_count}")


@app.command("list")
def list_words() -> None:
    """List all stored words."""
    settings = get_settings()
    repo = get_repo(settings)
    items = repo.list_words()

    if not items:
        typer.echo("No words found.")
        return

    for item in items:
        typer.echo(f"- {item.word}: {item.meaning}")


@app.command()
def review(count: Annotated[int, typer.Option(help="Number of words")] = 5) -> None:
    """Show words to review and update review stats."""
    settings = get_settings()
    repo = get_repo(settings)
    items = repo.review_candidates(count=count)

    if not items:
        typer.echo("No words found.")
        return

    for item in items:
        typer.echo(f"[{item.word}] {item.meaning}")
        typer.echo(f"  usage: {item.usage}")
        typer.echo(f"  pattern: {item.pattern}")
        repo.mark_reviewed(item.word)


@app.command()
def delete(word: str) -> None:
    """Delete one word."""
    settings = get_settings()
    repo = get_repo(settings)
    deleted = repo.delete_word(word)
    if not deleted:
        raise typer.Exit(code=1)
    typer.echo(f"Deleted word: {word.lower()}")


def main() -> None:
    app()
