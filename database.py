"""Database configuration and models for PostgreSQL.

Usage:
    db = Database()
    db.init_db()
    session = db.get_db()
    # ... use session
    session.close()
    db.close_db()
"""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

# Module exports
__all__ = ['Database', 'Ad']

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

class Database:
    """Database manager class that handles SQLAlchemy connections and sessions."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize the Database instance.

        Args:
            database_url: Optional database URL. If not provided, uses the default from environment.
        """
        self.database_url = database_url or DATABASE_URL
        self.engine: Optional[Engine] = None
        self.session_local: Optional[sessionmaker] = None

    def init_db(self) -> Engine:
        """Initialize database connection and create tables."""
        self.engine = create_engine(self.database_url)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Create tables
        Base.metadata.create_all(bind=self.engine)

        return self.engine

    def get_db(self) -> Session:
        """Get database session."""
        if self.session_local is None:
            self.init_db()

        db = self.session_local()
        try:
            return db
        except Exception:
            db.close()
            raise

    def close_db(self):
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.session_local = None

    def destroy_db(self):
        """Drop all tables and destroy the database schema."""
        if self.engine is None:
            self.init_db()

        # Drop all tables
        Base.metadata.drop_all(bind=self.engine)

        # Clean up connections
        if self.session_local:
            self.session_local.close_all()
            self.session_local = None

        if self.engine:
            self.engine.dispose()
            self.engine = None

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

