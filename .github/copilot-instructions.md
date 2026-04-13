# Copilot Instructions

## Language and Comment Policy

- Write source code, comments, commit messages, and user-facing strings in English.
- Keep comments concise and only when they add context not obvious from code.
- Prefer clear names and readable structure instead of explanatory comments.

## Engineering Principles

- Avoid duplicated logic; refactor shared behavior into helper functions.
- Keep modules focused and small.
- Preserve backward-compatible CLI behavior unless explicitly changed.

## Testing and Quality

- Add or update unit tests for all new behaviors.
- Mock network-dependent code in tests.
- Keep lint and tests green in CI.
