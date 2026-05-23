import os
import pytest
from shared.config import Settings, settings

def test_settings_load_model_tier():
    os.environ["MODEL_TIER"] = "1"
    os.environ["OLLAMA_HOST"] = "http://localhost:11434"
    os.environ["OLLAMA_PRIMARY_MODEL"] = "llama3.1:8b"
    os.environ["OLLAMA_RESEARCH_MODEL"] = "mistral:7b"
    os.environ["OLLAMA_SHADOW_MODEL"] = "phi3:mini"
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = "6379"
    os.environ["REDIS_DB"] = "0"
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5432"
    os.environ["DB_NAME"] = "hedgefund"
    os.environ["DB_USER"] = "hedgefund"
    os.environ["DB_PASSWORD"] = "changeme"
    os.environ["PAPER_TRADING"] = "true"

    settings = Settings()
    assert settings.model_tier == 1
    assert settings.ollama_primary_model == "llama3.1:8b"
    assert settings.paper_trading is True

def test_settings_redis_url():
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = "6379"
    os.environ["REDIS_DB"] = "0"
    settings = Settings()
    assert settings.redis_url == "redis://localhost:6379/0"

def test_settings_db_dsn():
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5432"
    os.environ["DB_NAME"] = "hedgefund"
    os.environ["DB_USER"] = "hedgefund"
    os.environ["DB_PASSWORD"] = "changeme"
    settings = Settings()
    assert "hedgefund" in settings.db_dsn

def test_settings_stock_watchlist_default():
    settings = Settings()
    assert settings.stock_watchlist == "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,SPY,QQQ"

def test_settings_crypto_watchlist_default():
    settings = Settings()
    assert settings.crypto_watchlist == "BTCUSDT,ETHUSDT,SOLUSDT"

def test_settings_reddit_defaults():
    settings = Settings()
    assert settings.reddit_client_id == ""
    assert settings.reddit_client_secret == ""

def test_settings_kelly_multiplier_default():
    assert settings.kelly_multiplier == 0.25

def test_settings_risk_max_position_pct_default():
    assert settings.risk_max_position_pct == 0.10

def test_settings_risk_max_positions_default():
    assert settings.risk_max_positions == 10

def test_settings_initial_capital_default():
    assert settings.initial_capital == 100_000.0
