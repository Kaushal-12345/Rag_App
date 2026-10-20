"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration. Model names live here so they can be swapped easily."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_provider: str = "openai_compatible"
    ollama_base_url: str = "http://localhost:11434/v1"

    llm_model_1: str = "openai/gpt-oss-120b"
    llm_model_2: str = "qwen/qwen3.8-27b"
    llm_model_3: str = "openai/gpt-oss-20b"
    default_llm_model: str = "openai/gpt-oss-120b"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    chunk_size_tokens: int = Field(default=600, ge=50)
    chunk_overlap_tokens: int = Field(default=100, ge=0)
    retrieve_top_k: int = Field(default=5, ge=1, le=50)

    chroma_path: Path = BACKEND_ROOT / "data" / "vector_db"
    upload_dir: Path = BACKEND_ROOT / "data" / "uploads"

    log_level: str = "INFO"
    cors_origins: str = "https://rag-app-one-zeta.vercel.app/"
    llm_timeout_seconds: float = 90.0

    # Web search (Tavily is primary; DuckDuckGo via `ddgs` is the fallback).
    tavily_api_key: str = ""
    web_search_max_results: int = Field(default=4, ge=1, le=10)

    # Optional cross-encoder reranking of retrieved chunks.
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_multiplier: int = Field(default=3, ge=1, le=10)

    # Conversation memory sent to the LLM (messages, not turns).
    max_history_messages: int = Field(default=6, ge=0, le=20)

    # Safety limits.
    max_upload_mb: int = Field(default=25, ge=1, le=200)
    rate_limit_per_minute: int = Field(default=60, ge=1)

    # Optional fallbacks.
    ocr_enabled: bool = True  # needs the `tesseract` binary; skipped quietly if missing
    whisper_fallback: bool = False  # needs `pip install -r requirements-optional.txt`
    whisper_model: str = "base"

    @property
    def llm_models(self) -> tuple[str, str, str]:
        """The three configured open-source model IDs."""
        return (self.llm_model_1, self.llm_model_2, self.llm_model_3)

    def resolved_model(self, requested: str | None) -> str:
        """Return a configured model id, falling back to the default."""
        if requested and requested in self.llm_models:
            return requested
        if self.default_llm_model in self.llm_models:
            return self.default_llm_model
        return self.llm_model_1

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    settings = Settings()
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings