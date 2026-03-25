"""
src/config.py
=============
Configurações centralizadas via .env ou variáveis de ambiente.

Uso:
    from src.config import settings, BASE_DIR
"""
from __future__ import annotations
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "interchange-ai"
    database_url: str = "sqlite+pysqlite:///./interchange_ai.db"
    sample_csv_path: str = "data/sample_interchange_rules.csv"

    # Qual provedor LLM usar: anthropic | openai | gemini | ollama
    llm_provider: str = "anthropic"
    enable_llm_normalization: bool = False

    # Anthropic Claude
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = "claude-sonnet-4-20250514"

    # OpenAI (também compatível com Azure OpenAI / proxies)
    openai_api_key: str | None = Field(default=None)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    # Google Gemini
    google_api_key: str | None = Field(default=None)
    gemini_model: str = "gemini-1.5-flash"

    # Ollama (LLM local, zero custo)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False,
    )


settings = Settings()
BASE_DIR: Path = Path(__file__).resolve().parents[1]
