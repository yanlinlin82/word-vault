#!/bin/bash

WORD_VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_word_vault_run() {
    (
        cd "$WORD_VAULT_DIR" || exit 1
        uv run word-vault "$@"
    )
}

_word_vault_complete_word_show() {
    local current words

    current="${COMP_WORDS[COMP_CWORD]}"
    words="$(_word_vault_run list "${current}*" 2>/dev/null | awk '/^- / {print $2}')"
    COMPREPLY=( $(compgen -W "$words" -- "$current") )
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

complete -F _word_vault_complete_word_show word-show
