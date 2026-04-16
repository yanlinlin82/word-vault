from __future__ import annotations

from typing import Annotated

import typer

from .config import Settings, get_settings
from .models import WordEntry
from .services.llm_client import DeepSeekClient
from .storage import WordRepository

app = typer.Typer(
    help="Word Vault CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


def get_repo(settings: Settings) -> WordRepository:
    return WordRepository(settings.db_path)


def get_deepseek_client(settings: Settings) -> DeepSeekClient:
    return DeepSeekClient(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )


def echo_word_details(item: WordEntry) -> None:
    typer.echo(f"Word: {item.word}")
    typer.echo(f"Phonetic: {item.phonetic}")
    typer.echo(f"Meaning: {item.meaning}")
    typer.echo(f"Usage: {item.usage}")
    typer.echo(f"Pattern: {item.pattern}")
    typer.echo(f"Source sentence: {item.source_sentence}")
    typer.echo(f"Example count: {item.example_count}")
    typer.echo(f"Review count: {item.review_count}")


def echo_word_examples(repo: WordRepository, word: str) -> None:
    examples = repo.list_examples(word)
    if not examples:
        return
    typer.echo("Examples:")
    for example in examples:
        primary = " [primary]" if example.is_primary else ""
        typer.echo(f"- {example.sentence} (seen: {example.seen_count}){primary}")


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
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Force refresh from DeepSeek even if the word already exists.",
        ),
    ] = False,
) -> None:
    """Add a word with cache-first behavior and optional LLM refresh."""
    settings = get_settings()
    repo = get_repo(settings)

    existing = repo.get_word(word)
    if existing and not refresh:
        if sentence:
            added = repo.add_sentence_example(word=word, sentence=sentence, source_type="user")
            if added:
                typer.echo(f"Added new sentence example for: {word.lower()}")
            else:
                typer.echo(f"Sentence already exists for: {word.lower()} (seen count increased)")

            item = repo.get_word(word)
            if item is None:
                raise typer.Exit(code=1)
            echo_word_details(item)
            echo_word_examples(repo, word)
            return

        typer.echo(
            f"Word already exists in local vault: {word.lower()}. "
            "Use --refresh to fetch from DeepSeek again."
        )
        return

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
    if existing:
        typer.echo(f"Updated word from DeepSeek: {word.lower()}")
    else:
        typer.echo(f"Saved word: {word.lower()}")

    item = repo.get_word(word)
    if item is None:
        raise typer.Exit(code=1)

    echo_word_details(item)
    echo_word_examples(repo, word)


@app.command()
def show(word: str) -> None:
    """Show details of one word."""
    settings = get_settings()
    repo = get_repo(settings)
    item = repo.get_word(word)

    if item is None:
        raise typer.Exit(code=1)

    echo_word_details(item)
    echo_word_examples(repo, word)


@app.command("list")
def list_words(
    pattern: Annotated[
        str | None,
        typer.Argument(help="Optional wildcard pattern using * and ?"),
    ] = None,
) -> None:
    """List all stored words, optionally filtered by wildcard pattern."""
    settings = get_settings()
    repo = get_repo(settings)
    items = repo.list_words(pattern=pattern)

    if not items:
        typer.echo("No words found.")
        return

    for item in items:
        typer.echo(f"- {item.word} {item.phonetic}: {item.meaning}")


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
