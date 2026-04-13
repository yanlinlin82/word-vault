# Overview

Word Vault is a personal command-line tool for English vocabulary learning.

## Goals

- Save words with LLM-generated learning context.
- Keep a local, inspectable knowledge base.
- Support repeated review over time.

## Current MVP Scope

- Add word from DeepSeek response.
- Show one word.
- List all words.
- Review words and update review counters.
- Delete one word.

## Architecture

- CLI: Typer commands.
- Service: DeepSeek API client.
- Storage: SQLite repository.
- Config: `.env` + environment variables.
