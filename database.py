"""Database configuration and models for PostgreSQL."""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "pincrawl")
DB_USER = os.getenv("DB_USER", "pincrawl")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pincrawl")

# Create database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy setup
Base = declarative_base()
engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None

class Ad(Base):
    """SQLAlchemy model for ads table."""

    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    ignored = Column(Boolean, default=False, nullable=False)
    retries = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    amount = Column(Integer, nullable=True)  # Price amount in cents/smallest currency unit
    currency = Column(String, nullable=True)  # Currency code (EUR, USD, etc.)
    city = Column(String, nullable=True)  # City where the item is located
    zipcode = Column(String, nullable=True)  # Zipcode where the item is located
    product = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    year = Column(String, nullable=True)
    opdb_id = Column(String, nullable=True)
    scraped_at = Column(DateTime, nullable=True)
    identified_at = Column(DateTime, nullable=True)
    scrape_id = Column(String, nullable=True)

def init_db():
    """Initialize database connection and create tables."""
    global engine, SessionLocal

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    return engine


def get_db() -> Session:
    """Get database session."""
    if SessionLocal is None:
        init_db()

    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise

def close_db():
    """Close database connection."""
    global engine
    if engine:
        engine.dispose()


def destroy_db():
    """Drop all tables and destroy the database schema."""
    global engine, SessionLocal

    if engine is None:
        init_db()

    # Drop all tables
    Base.metadata.drop_all(bind=engine)

    # Reset global variables
    if SessionLocal:
        SessionLocal.close_all()
        SessionLocal = None

    if engine:
        engine.dispose()
        engine = None
