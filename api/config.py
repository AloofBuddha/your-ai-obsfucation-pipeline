"""Runtime configuration — loaded from environment / .env."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL"
    )

    obfuscation_strategy_default: str = Field(
        default="tokenize", alias="OBFUSCATION_STRATEGY"
    )
    detection_confidence_threshold: float = Field(
        default=0.6, alias="DETECTION_CONFIDENCE_THRESHOLD"
    )

    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com/", alias="LANGSMITH_ENDPOINT"
    )
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="secure-context-pipeline", alias="LANGSMITH_PROJECT"
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    data_dir: str = Field(default="data", alias="DATA_DIR")
    audit_path: str = Field(default="audit.jsonl", alias="AUDIT_PATH")
    vault_db_path: str = Field(default="data/vault.db", alias="VAULT_DB_PATH")
    user_keys_path: str = Field(
        default="data/user_keys.json", alias="USER_KEYS_PATH"
    )

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
