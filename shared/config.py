from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    model_tier: int = Field(default=1, ge=1, le=3)

    ollama_host: str = "http://localhost:11434"
    ollama_primary_model: str = "llama3.1:8b"
    ollama_research_model: str = "mistral:7b"
    ollama_shadow_model: str = "phi3:mini"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "hedgefund"
    db_user: str = "hedgefund"
    db_password: str = "changeme"

    paper_trading: bool = True

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    binance_api_key: str = ""
    binance_secret_key: str = ""
    news_api_key: str = ""
    fred_api_key: str = ""
    gmail_sender: str = ""

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def db_dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
