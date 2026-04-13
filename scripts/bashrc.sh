#!/bin/bash

WORD_VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_word_vault_run() {
    (
        cd "$WORD_VAULT_DIR" || exit 1
        uv run word-vault "$@"
    )
}

word-add() {
    _word_vault_run add "$@"
}

word-show() {
    _word_vault_run show "$@"
}

word-list() {
    _word_vault_run list "$@"
}

word-review() {
    _word_vault_run review "$@"
}

word-delete() {
    _word_vault_run delete "$@"
}
