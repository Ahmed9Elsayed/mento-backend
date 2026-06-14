from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR

# Model directories are now co-located inside the repo under models/
MODELS_DIR = BASE_DIR / "models"


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    project_root: Path = PROJECT_ROOT

    # Updated paths — models now live inside the repo
    module1_models_dir_local: Path = MODELS_DIR / "module1"
    module1_models_dir_space: Path = MODELS_DIR / "module1"
    module2_model_dir: Path = MODELS_DIR / "module2" / "emotion_classifier"

    groq_api_key: str = ""
    intent_groq_api_key: str = ""
    rag_groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    intent_groq_model: str = "llama-3.3-70b-versatile"
    rag_groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.3
    groq_max_tokens: int = 700

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "Mental-Health-Counseling-Embeddings"
    qdrant_vector_name: str | None = None

    dataset_name: str = "Amod/mental_health_counseling_conversations"
    dataset_split: str = "train"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 900
    chunk_overlap: int = 120
    retriever_k: int = 4
    max_dataset_rows: int = 0
    force_rebuild_index: bool = False
    build_index_on_startup: bool = False
    use_local_emotion_model: bool = True
    min_available_pagefile_mb: int = 4096
    min_embedding_pagefile_mb: int = 0

    feedback_google_sheet_id: str = "1Ja4NI2w9YbG6rw623bRDoamtm8YrSmeaChJ44xeuiyY"
    feedback_google_worksheet_gid: int = 0
    feedback_google_worksheet_name: str = ""
    google_service_account_json: str = ""
    google_service_account_json_b64: str = ""
    google_service_account_file: str = ""
    feedback_apps_script_url: str = ""
    feedback_apps_script_secret: str = ""
    feedback_apps_script_timeout: float = 10.0

    langsmith_project: str = "Mental Health Rag ChatBot"
    flask_host: str = "0.0.0.0"
    flask_port: int = 5000
    flask_debug: bool = False


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    langsmith_project = (
        os.getenv("LANGSMITH_PROJECT")
        or os.getenv("LANGCHAIN_PROJECT")
        or "Mental Health Rag ChatBot"
    )
    if langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", langsmith_project)
        os.environ.setdefault("LANGCHAIN_PROJECT", langsmith_project)
    if os.getenv("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")

    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        intent_groq_api_key=os.getenv("INTENT_GROQ_API_KEY")
        or os.getenv("GROQ_API_KEY", ""),
        rag_groq_api_key=os.getenv("RAG_GROQ_API_KEY") or os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        intent_groq_model=os.getenv("INTENT_GROQ_MODEL")
        or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        rag_groq_model=os.getenv("RAG_GROQ_MODEL")
        or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_temperature=_float_env("GROQ_TEMPERATURE", 0.3),
        groq_max_tokens=_int_env("GROQ_MAX_TOKENS", 700),
        qdrant_url=os.getenv("QDRANT_URL", ""),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "Mental-Health"),
        qdrant_vector_name=os.getenv("QDRANT_VECTOR_NAME") or None,
        dataset_name=os.getenv(
            "DATASET_NAME", "Amod/mental_health_counseling_conversations"
        ),
        dataset_split=os.getenv("DATASET_SPLIT", "train"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        chunk_size=_int_env("CHUNK_SIZE", 900),
        chunk_overlap=_int_env("CHUNK_OVERLAP", 120),
        retriever_k=_int_env("RETRIEVER_K", 4),
        max_dataset_rows=_int_env("MAX_DATASET_ROWS", 0),
        force_rebuild_index=_bool_env("FORCE_REBUILD_INDEX", False),
        build_index_on_startup=_bool_env("BUILD_INDEX_ON_STARTUP", False),
        use_local_emotion_model=_bool_env("USE_LOCAL_EMOTION_MODEL", True),
        min_available_pagefile_mb=_int_env("MIN_AVAILABLE_PAGEFILE_MB", 4096),
        min_embedding_pagefile_mb=_int_env("MIN_EMBEDDING_PAGEFILE_MB", 0),
        feedback_google_sheet_id=os.getenv(
            "FEEDBACK_GOOGLE_SHEET_ID",
            "1Ja4NI2w9YbG6rw623bRDoamtm8YrSmeaChJ44xeuiyY",
        ),
        feedback_google_worksheet_gid=_int_env("FEEDBACK_GOOGLE_WORKSHEET_GID", 0),
        feedback_google_worksheet_name=os.getenv(
            "FEEDBACK_GOOGLE_WORKSHEET_NAME", ""
        ),
        google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        google_service_account_json_b64=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64", ""
        ),
        google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
        feedback_apps_script_url=os.getenv("FEEDBACK_APPS_SCRIPT_URL", ""),
        feedback_apps_script_secret=os.getenv("FEEDBACK_APPS_SCRIPT_SECRET", ""),
        feedback_apps_script_timeout=_float_env("FEEDBACK_APPS_SCRIPT_TIMEOUT", 10.0),
        langsmith_project=langsmith_project,
        flask_host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
        flask_port=_int_env("FLASK_RUN_PORT", 5000),
        flask_debug=_bool_env("FLASK_DEBUG", False),
    )
