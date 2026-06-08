# gateway/database.py
"""
SQLAlchemy database session management for the hedge fund system.
Provides SessionLocal for ORM operations across all modules.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Build database URL from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "hedgefund")
DB_USER = os.getenv("DB_USER", "hedgefund")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
