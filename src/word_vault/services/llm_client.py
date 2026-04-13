from __future__ import annotations

import json
import re

import httpx


class DeepSeekClient:
    def __init__(self, *, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def fetch_word_info(self, word: str, sentence: str | None = None) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required.")

        prompt = self._build_prompt(word=word, sentence=sentence)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an English learning assistant. "
                        "Return strict JSON only, with no prose or markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        raw = data["choices"][0]["message"]["content"]
        cleaned_json = self._extract_json(raw)
        parsed = json.loads(cleaned_json)

        required = ["phonetic", "meaning", "usage", "pattern", "example_sentence"]
        missing = [key for key in required if key not in parsed]
        if missing:
            raise RuntimeError(f"DeepSeek response missing required fields: {', '.join(missing)}")

        return {
            "phonetic": str(parsed["phonetic"]).strip(),
            "meaning": str(parsed["meaning"]).strip(),
            "usage": str(parsed["usage"]).strip(),
            "pattern": str(parsed["pattern"]).strip(),
            "example_sentence": str(parsed["example_sentence"]).strip(),
        }

    @staticmethod
    def _build_prompt(word: str, sentence: str | None = None) -> str:
        sentence_hint = sentence.strip() if sentence else ""
        return (
            "Analyze the English word and return a JSON object with keys: "
            "phonetic, meaning, usage, pattern, example_sentence. "
            "Keep each value concise and practical for learners. "
            f"Word: {word}. "
            f"Optional context sentence: {sentence_hint}."
        )

    @staticmethod
    def _extract_json(raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("{") and text.endswith("}"):
            return text

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if fenced:
            return fenced.group(1)

        brace_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
        if brace_match:
            return brace_match.group(1)

        raise RuntimeError("DeepSeek response did not contain valid JSON.")
