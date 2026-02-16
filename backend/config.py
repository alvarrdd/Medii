from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_BASE_DIR: Path = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    base_dir: Path = _BASE_DIR
    data_dir: Path = base_dir / "data"
    # Be flexible with filenames present in repo
    medical_knowledge_csv: Path = data_dir / "medical_knowledge.csv"
    disease_specialist_csv: Path = data_dir / "disease_specialists.csv"
    faiss_index_path: Path = data_dir / "symptom_index.faiss"

    # Default to MiniLM as per project description; allow override via env EMBEDDING_MODEL
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    max_context_chars: int = int(os.getenv("MAX_CONTEXT_CHARS", "2800"))

    gemini_model_name: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.25"))

    disclaimer: str = (
        "Այս տեղեկատվությունը բժշկական ախտորոշում չէ։ "
        "Խնդրում ենք անպայման խորհրդակցել որակավորված բժշկի հետ։"
    )


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance