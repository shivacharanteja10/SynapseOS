"""Runtime configuration for SynapseOS."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "SynapseOS"
    environment: Literal["local", "staging", "production", "test"] = "local"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    openai_api_key: str | None = None
    llm_provider: Literal["mock", "openai"] = "mock"
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.2

    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "synapseos"
    langsmith_endpoint: str | None = "https://api.smith.langchain.com"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://synapseos:synapseos@localhost:5432/synapseos"

    vector_backend: Literal["memory", "qdrant", "chroma"] = "memory"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "synapseos_knowledge"
    chroma_persist_dir: str = "./.chroma"
    embedding_dimensions: int = 384

    human_approval_required_risk_score: float = 0.72
    max_agent_iterations: int = 10
    task_queue_name: str = "synapseos:tasks"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        return ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for dependency injection."""

    return Settings()
