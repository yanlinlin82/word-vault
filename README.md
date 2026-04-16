# Word Vault

A personal command-line tool for looking up English words, saving meanings, phonetics, usage, and example sentences, and reviewing them over time to strengthen memory.

## Tech Stack

- Python 3.11+
- Typer for CLI
- SQLite for local storage
- DeepSeek API for LLM enrichment
- python-dotenv for environment config
- espeak-ng or espeak for optional IPA-based audio playback

## Project Layout

```text
word-vault/
├── docs/
├── src/
│   └── word_vault/
├── tests/
└── pyproject.toml
```

## Quick Start

1. Install dependencies:

    ```bash
    uv sync
    ```

2. Create local environment file:

    ```bash
    cp .env.example .env
    ```

3. Set your `DEEPSEEK_API_KEY` in `.env`.

4. Initialize database schema:

    ```bash
    uv run word-vault init-db
    ```

## Basic Commands

```bash
uv run word-vault add apple --sentence "I ate an apple after lunch."
uv run word-vault add apple --refresh
uv run word-vault show apple
uv run word-vault show apple --speak
uv run word-vault speak apple
uv run word-vault list
uv run word-vault list 'app*'
uv run word-vault review --count 5
uv run word-vault delete apple
```

`add` uses cache-first behavior by default to avoid repeated LLM calls.
Use `--refresh` only when you want to fetch a new result from DeepSeek.
`list` supports `*` and `?` wildcards; quote patterns in the shell.
`add` tries to play local audio from the stored IPA phonetic field when `espeak-ng` or `espeak` is available.
`show` is mute by default; pass `--speak` when you want spoken output.
`speak` is audio-only and uses the stored IPA pronunciation.
`review` merges dictation, meaning recognition, example-sentence practice, and recall scoring in one flow. It uses IPA/audio for dictation, asks a meaning multiple-choice question using other stored words as distractors, plays example sentences to reinforce usage, and then schedules future reviews with an SM-2 style forgetting-curve strategy.

Disable audio with `WORD_VAULT_AUDIO_ENABLED=0`.
Set a specific voice with `WORD_VAULT_AUDIO_VOICE`, for example `en-us`.

## Development Commands

Use direct uv entrypoints as the primary workflow:

```bash
uv run word-vault init-db
uv run ruff check .
uv run pytest
```

## Bash Shortcuts

You can source helper functions from [scripts/bashrc.sh](scripts/bashrc.sh):

```bash
source /work/Projects/Personal/word-vault/scripts/bashrc.sh
```

Or add this line to your `~/.bashrc`:

```bash
source /work/Projects/Personal/word-vault/scripts/bashrc.sh
```

Then use shortcuts such as:

```bash
word-add apple --sentence "I ate an apple after lunch."
word-list
word-show apple
word-show apple --speak
word-speak apple
word-review --count 5
word-delete apple
```

After sourcing [scripts/bashrc.sh](scripts/bashrc.sh), `word-show` also supports Bash Tab completion based on stored words.

## Docs

- `docs/overview.md`
- `docs/cli.md`
- `docs/development.md`
