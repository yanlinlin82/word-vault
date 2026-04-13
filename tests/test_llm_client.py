from __future__ import annotations

import json

from word_vault.services.llm_client import DeepSeekClient


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_fetch_word_info_fallback_when_invalid_proxy_scheme(monkeypatch) -> None:
    client = DeepSeekClient(
        api_key="test-key",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
    )

    calls: list[bool] = []

    def fake_post(url, headers, json, timeout, trust_env):
        calls.append(trust_env)
        if trust_env:
            raise ValueError("Unknown scheme for proxy URL URL('socks://localhost:1090')")

        payload = {
            "choices": [
                {
                    "message": {
                        "content": json_dumps(
                            {
                                "phonetic": "/ap.əl/",
                                "meaning": "a fruit",
                                "usage": "noun",
                                "pattern": "eat an apple",
                                "example_sentence": "I ate an apple.",
                            }
                        )
                    }
                }
            ]
        }
        return FakeResponse(payload)

    monkeypatch.setattr("word_vault.services.llm_client.httpx.post", fake_post)

    result = client.fetch_word_info("apple")

    assert calls == [True, False]
    assert result["meaning"] == "a fruit"


def json_dumps(value: dict[str, str]) -> str:
    return json.dumps(value, ensure_ascii=True)
