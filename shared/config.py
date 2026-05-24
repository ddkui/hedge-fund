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
    gmail_app_password: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "hedgefund/1.0"

    stock_watchlist: str = "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,SPY,QQQ"
    crypto_watchlist: str = "BTCUSDT,ETHUSDT,SOLUSDT"

    kelly_multiplier: float = 0.25
    risk_max_position_pct: float = 0.10
    risk_max_positions: int = 10
    risk_max_drawdown_pct: float = 0.20
    risk_var_limit_pct: float = 0.05
    risk_max_correlated: int = 3
    initial_capital: float = 100_000.0
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    binance_base_url: str = "https://api.binance.com"

    gateway_port: int = 8000
    jwt_secret: str = "dev-secret-change-in-production"
    dashboard_password: str = "hedgefund2026"

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def db_dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()

# Warn loudly if production-unsafe defaults are still in place
import warnings as _warnings
if settings.jwt_secret == "dev-secret-change-in-production":
    _warnings.warn(
        "JWT_SECRET is using the insecure default. "
        "Set JWT_SECRET in your .env before going live.",
        stacklevel=2,
    )
if settings.dashboard_password == "hedgefund2026":
    _warnings.warn(
        "DASHBOARD_PASSWORD is using the insecure default. "
        "Set DASHBOARD_PASSWORD in your .env before going live.",
        stacklevel=2,
    )
