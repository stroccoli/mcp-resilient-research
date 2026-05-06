from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Search providers ──────────────────────────────────────────────────────
    brave_api_key: str = ""
    serpapi_key: str = ""

    # ── LLM backend ───────────────────────────────────────────────────────────
    litellm_model: str = "ollama/llama3.1"
    litellm_api_base: str = "http://localhost:11434"

    # ── Query generation ──────────────────────────────────────────────────────
    # "deterministic" uses hand-crafted templates (no LLM call, default).
    # "llm" asks the configured LLM to generate the query set; falls back to
    # deterministic if the LLM call fails.
    query_generation_mode: Literal["deterministic", "llm"] = "deterministic"

    # ── Evaluation thresholds ─────────────────────────────────────────────────
    min_confidence_score: float = Field(default=0.4, ge=0.0, le=1.0)
    min_authority_level: Literal["High", "Medium", "Low"] = "Low"

    # ── Retry & backoff ───────────────────────────────────────────────────────
    max_retry_count: int = Field(default=3, ge=0)
    backoff_base_delay: float = Field(default=1.0, gt=0)
    backoff_max_delay: float = Field(default=30.0, gt=0)

    # ── Composite score weights ───────────────────────────────────────────────
    # confidence_score = authority_weight * authority_score
    #                  + relevance_weight * relevance_score
    authority_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    relevance_weight: float = Field(default=0.6, ge=0.0, le=1.0)

    # ── Database ──────────────────────────────────────────────────────────────
    database_path: str = "./research.db"


settings = Settings()
