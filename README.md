# Word Vault

A personal command-line tool for looking up English words, saving meanings, phonetics, usage, and example sentences, and reviewing them over time to strengthen memory.

## Tech Stack

- Python 3.11+
- Typer for CLI
- SQLite for local storage
- DeepSeek API for LLM enrichment
- python-dotenv for environment config

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
uv run word-vault list
uv run word-vault review --count 5
uv run word-vault delete apple
```

`add` uses cache-first behavior by default to avoid repeated LLM calls.
Use `--refresh` only when you want to fetch a new result from DeepSeek.

## Development Commands

Use direct uv entrypoints as the primary workflow:

```bash
uv run word-vault init-db
uv run ruff check .
uv run pytest
```

## Docs

- `docs/overview.md`
- `docs/cli.md`
- `docs/development.md`
