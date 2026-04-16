from __future__ import annotations

from word_vault.services.audio import ipa_to_espeak_phonemes


def test_ipa_to_espeak_phonemes_handles_common_english_ipa() -> None:
    assert ipa_to_espeak_phonemes("/ˈæp.əl/") == "'a p @ l"
    assert ipa_to_espeak_phonemes("/bəˈnæn.ə/") == "b @ n 'a n @"


def test_ipa_to_espeak_phonemes_returns_none_for_unknown_symbols() -> None:
    assert ipa_to_espeak_phonemes("/🙂/") is None