from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    db_path: Path
    deepseek_api_key: str
    deepseek_model: str
    deepseek_base_url: str


def get_settings() -> Settings:
    load_dotenv()

    db_path = Path(os.getenv("WORD_VAULT_DB_PATH", "data/word_vault.db"))
    return Settings(
        db_path=db_path,
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip(),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
    )
