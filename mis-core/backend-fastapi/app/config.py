"""
app/config.py
=============

Configuração centralizada via Pydantic Settings — lê de variáveis de ambiente
e/ou arquivo .env, com validação de tipos e defaults seguros.

Analogia WCM: isto é o "setup sheet" do serviço. Cada parâmetro aqui é um
registro documentado do comportamento esperado — sem settings mágicos
espalhados por strings os.getenv().
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Todas as configs do serviço. Lê variáveis em ordem:
      1. ENV var com mesmo nome (MAIÚSCULO)
      2. .env no cwd
      3. default definido aqui
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Aplicação ---
    app_name: str = "mis-core-fastapi"
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    api_v2_prefix: str = "/api/v2"

    # --- CORS ---
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Origens permitidas pelo CORS (lista explícita em prod)",
    )

    # --- InfluxDB ---
    influx_host: str = "localhost"
    influx_port: int = 8086
    influx_db: str = "mis"
    influx_username: str = ""
    influx_password: str = ""
    influx_timeout_s: int = 10

    # --- Django legacy (durante migração Strangler) ---
    django_api_url: str = "http://mis-core-django:8000/api"
    django_timeout_s: int = 5

    # --- Flask legacy (durante migração Strangler) ---
    flask_api_url: str = "http://mis-core-flask:5000/api"

    # --- JWT (shared secret com Django SIMPLE_JWT) ---
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"

    # --- Postgres (para metadata e agregações históricas) ---
    pg_dsn: str = "postgresql://user:pass@localhost:5432/mis_core"

    # --- Observability ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    prometheus_enabled: bool = True

    # --- Limites de segurança/performance ---
    max_points_per_response: int = 10_000
    max_correlation_variables: int = 25


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton — instância única compartilhada entre todos os handlers."""
    return Settings()
