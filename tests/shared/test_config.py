import os
import pytest
from shared.config import Settings

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
