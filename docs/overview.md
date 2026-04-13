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

## LLM Strategy

- Cache-first by default: if a word already exists, skip repeated LLM calls.
- Explicit refresh: call DeepSeek only when user passes `--refresh`.
- Structured output: enforce fixed JSON schema in prompts and parse strictly.
