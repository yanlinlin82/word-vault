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
                        "Output must be valid JSON only, without prose, markdown, or code fences. "
                        "Do not add extra keys beyond the required schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        response = self._post_chat_completion(payload)
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

    def _post_chat_completion(self, payload: dict[str, object]) -> httpx.Response:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            return httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
                trust_env=True,
            )
        except ValueError as exc:
            if "Unknown scheme for proxy URL" not in str(exc):
                raise

            return httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
                trust_env=False,
            )

    @staticmethod
    def _build_prompt(word: str, sentence: str | None = None) -> str:
        sentence_hint = sentence.strip() if sentence else ""
        return (
            "Analyze the target English word and return one JSON object using exactly this schema: "
            "{\"phonetic\": string, \"meaning\": string, \"usage\": string, \"pattern\": string, "
            "\"example_sentence\": string}. "
            "Rules: each value must be plain text, concise, learner-friendly, and non-empty. "
            "Do not include markdown, comments, or additional keys. "
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
