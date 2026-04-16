# Development Rules

## Code Style

- Use English for user-facing strings, code comments, and documentation.
- Keep comments minimal and meaningful.
- Prefer self-explanatory naming and clear function boundaries.
- Reduce duplication by extracting reusable helpers.

## Project Practices

- Keep business logic in `src/word_vault/`.
- Keep tests in `tests/` and mock external APIs.
- Mock audio playback in tests; do not invoke real `espeak`/`espeak-ng` from unit tests.
- Keep docs in `docs/` and update them when behavior changes.

## CI/CD Best Practices

- Run lint and tests on every pull request.
- Keep CI deterministic and fast.
- Fail fast on lint or unit test failures.
- Use pinned Python versions in CI matrix when stability matters.
- Protect main branch with required status checks.
