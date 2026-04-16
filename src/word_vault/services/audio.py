from __future__ import annotations

import re
import shutil
import subprocess

_MULTI_CHAR_IPA_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("dʒ", "dZ"),
    ("tʃ", "tS"),
    ("eɪ", "eI"),
    ("aɪ", "aI"),
    ("ɔɪ", "OI"),
    ("aʊ", "aU"),
    ("oʊ", "oU"),
    ("əʊ", "oU"),
    ("ɪə", "I@"),
    ("eə", "e@"),
    ("ʊə", "U@"),
    ("ju", "ju"),
)

_IPA_SYMBOLS = {
    "p": "p",
    "b": "b",
    "t": "t",
    "d": "d",
    "k": "k",
    "g": "g",
    "ɡ": "g",
    "f": "f",
    "v": "v",
    "θ": "T",
    "ð": "D",
    "s": "s",
    "z": "z",
    "ʃ": "S",
    "ʒ": "Z",
    "h": "h",
    "m": "m",
    "n": "n",
    "ŋ": "N",
    "l": "l",
    "r": "r",
    "ɹ": "r",
    "j": "j",
    "w": "w",
    "i": "i",
    "ɪ": "I",
    "e": "e",
    "ɛ": "E",
    "æ": "a",
    "ə": "@",
    "ʌ": "V",
    "ɑ": "A",
    "ɒ": "Q",
    "ɔ": "O",
    "ʊ": "U",
    "u": "u",
    "ɜ": "3",
    "ɚ": "@r",
    "ɝ": "3:r",
    "ː": ":",
    "ˈ": "'",
    "ˌ": ",",
}

_IGNORED_IPA_SYMBOLS = {"/", "[", "]", "(", ")", ".", " ", "-"}
_VOWEL_PHONEMES = {
    "i",
    "I",
    "e",
    "E",
    "a",
    "@",
    "V",
    "A",
    "Q",
    "O",
    "U",
    "u",
    "3",
    "3:",
    "@r",
    "3:r",
    "eI",
    "aI",
    "OI",
    "aU",
    "oU",
    "I@",
    "e@",
    "U@",
}


def play_word_audio(word: str, phonetic: str, *, voice: str = "en-us") -> bool:
    engine = _find_engine()
    if engine is None:
        return False

    speech_input = _build_speech_input(word=word, phonetic=phonetic)
    try:
        subprocess.run(
            [engine, "-v", voice, speech_input],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False

    return True


def play_text_audio(text: str, *, voice: str = "en-us") -> bool:
    engine = _find_engine()
    if engine is None:
        return False

    try:
        subprocess.run(
            [engine, "-v", voice, text],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False

    return True


def _build_speech_input(*, word: str, phonetic: str) -> str:
    espeak_phonemes = ipa_to_espeak_phonemes(phonetic)
    if espeak_phonemes:
        return f"[[{espeak_phonemes}]]"
    return word


def ipa_to_espeak_phonemes(phonetic: str) -> str | None:
    cleaned = phonetic.strip()
    if not cleaned:
        return None

    for source, target in _MULTI_CHAR_IPA_REPLACEMENTS:
        cleaned = cleaned.replace(source, target)

    tokens: list[str] = []
    pending_stress: str | None = None

    for char in cleaned:
        if char in _IGNORED_IPA_SYMBOLS:
            continue

        mapped = _IPA_SYMBOLS.get(char)
        if mapped is None:
            return None

        if mapped in {"'", ","}:
            pending_stress = mapped
            continue

        if mapped == ":":
            if not tokens:
                return None
            tokens[-1] = f"{tokens[-1]}:"
            continue

        if pending_stress and _is_vowel(mapped):
            mapped = f"{pending_stress}{mapped}"
            pending_stress = None

        tokens.append(mapped)

    if pending_stress:
        return None

    return re.sub(r"\s+", " ", " ".join(tokens)).strip() or None


def _is_vowel(phoneme: str) -> bool:
    normalized = phoneme.lstrip("',")
    return normalized in _VOWEL_PHONEMES


def _find_engine() -> str | None:
    for command in ("espeak-ng", "espeak"):
        path = shutil.which(command)
        if path:
            return path
    return None