from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://juryscan:juryscan@localhost:5432/juryscan"

    api_keys: str = ""
    cors_origins: str = "http://localhost:5173"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    ai_timeout_seconds: float = 60.0
    ai_max_retries: int = 1

    min_text_chars: int = 100
    max_text_chars: int = 200_000
    rate_limit_per_minute: int = 5
    store_input_text: bool = False

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
