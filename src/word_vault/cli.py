from __future__ import annotations

from typing import Annotated

import typer

from .config import Settings, get_settings
from .models import WordEntry
from .services.audio import play_word_audio
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


def maybe_play_audio(settings: Settings, item: WordEntry) -> None:
    if not settings.audio_enabled:
        return
    play_word_audio(word=item.word, phonetic=item.phonetic, voice=settings.audio_voice)


def prompt_quality_score() -> int:
    while True:
        quality = typer.prompt("Recall score (0-5, 5 = easy)", type=int, default=4)
        if 0 <= quality <= 5:
            return quality
        typer.echo("Please enter a number between 0 and 5.")


def spelling_score_from_attempts(word: str, first_attempt: str, second_attempt: str | None) -> int:
    normalized_word = word.strip().lower()
    if first_attempt.strip().lower() == normalized_word:
        return 5
    if second_attempt is not None and second_attempt.strip().lower() == normalized_word:
        return 3
    return 1


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
    sentence: Annotated[
        str | None,
        typer.Option("--sentence", "-s", help="Optional context sentence"),
    ] = None,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            "-r",
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
            maybe_play_audio(settings, item)
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
    maybe_play_audio(settings, item)


@app.command()
def show(
    word: str,
    speak: Annotated[
        bool,
        typer.Option("--speak", "-s", help="Speak word audio after showing details."),
    ] = False,
) -> None:
    """Show details of one word."""
    settings = get_settings()
    repo = get_repo(settings)
    item = repo.get_word(word)

    if item is None:
        raise typer.Exit(code=1)

    echo_word_details(item)
    echo_word_examples(repo, word)
    if speak:
        maybe_play_audio(settings, item)


@app.command()
def speak(word: str) -> None:
    """Speak one stored word using its IPA pronunciation."""
    settings = get_settings()
    repo = get_repo(settings)
    item = repo.get_word(word)

    if item is None:
        raise typer.Exit(code=1)

    if not settings.audio_enabled:
        typer.echo("Audio is disabled. Set WORD_VAULT_AUDIO_ENABLED=1 to enable it.")
        raise typer.Exit(code=1)

    ok = play_word_audio(word=item.word, phonetic=item.phonetic, voice=settings.audio_voice)
    if not ok:
        typer.echo("Unable to play audio. Install espeak-ng/espeak or check your audio setup.")
        raise typer.Exit(code=1)


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


@app.command("review")
def review(
    count: Annotated[int, typer.Option("--count", "-c", help="Number of words")] = 5,
) -> None:
    """Run interactive review with dictation and spaced-repetition scoring."""
    settings = get_settings()
    repo = get_repo(settings)
    items = repo.review_candidates(count=count)

    if not items:
        typer.echo("No words found.")
        return

    if not settings.audio_enabled:
        typer.echo("Audio is disabled. Running IPA-only dictation prompts.")

    for index, item in enumerate(items, start=1):
        typer.echo(f"\n--- Review {index}/{len(items)} ---")
        typer.echo(f"Phonetic: {item.phonetic}")
        maybe_play_audio(settings, item)

        first_attempt = typer.prompt("Spell the word")
        second_attempt: str | None = None
        if first_attempt.strip().lower() != item.word.lower():
            typer.echo("Not correct. Try once more.")
            second_attempt = typer.prompt("Spell the word (retry)")

        spelling_score = spelling_score_from_attempts(item.word, first_attempt, second_attempt)
        if spelling_score == 5:
            typer.echo("Spelling correct on first try.")
        elif spelling_score == 3:
            typer.echo("Spelling correct on retry.")
        else:
            typer.echo(f"Spelling not correct. Correct word: {item.word}")

        typer.echo(f"Meaning: {item.meaning}")
        typer.echo(f"Usage: {item.usage}")
        typer.echo(f"Pattern: {item.pattern}")
        typer.echo(f"Source sentence: {item.source_sentence}")

        recall_quality = prompt_quality_score()
        final_quality = min(recall_quality, spelling_score)
        repo.record_review_result(item.word, quality=final_quality)

        typer.echo(
            f"Saved review for {item.word}: final score={final_quality} "
            f"(recall={recall_quality}, spelling={spelling_score})"
        )


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
