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
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON, Index, UniqueConstraint, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from dotenv import load_dotenv
import enum

# Module exports
__all__ = ['Database', 'Ad', 'Sub', 'Task']

# Load environment variables
load_dotenv()

# Create database URL
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://pincrawl:pincrawl@localhost:5432/pincrawl")

# SQLAlchemy setup
Base = declarative_base()

class TaskStatus(enum.Enum):
    """Enum for task status values."""
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"

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

    # Define indexes for common query patterns
    __table_args__ = (
        # Index for filtering by ignored status and created_at (pagination/sorting)
        Index('ix_ads_ignored_created_at', 'ignored', 'created_at'),

        # Index for filtering by scraped status and scrape_id
        Index('ix_ads_scraped_at_scrape_id', 'scraped_at', 'scrape_id'),

        # Index for product matching queries
        Index('ix_ads_product_manufacturer', 'product', 'manufacturer'),

        # Index for location-based queries
        Index('ix_ads_city_zipcode', 'city', 'zipcode'),

        # Index for price range queries
        Index('ix_ads_currency_amount', 'currency', 'amount'),

        # Index for identifying processed ads
        Index('ix_ads_identified_at', 'identified_at'),

        # Index for OPDB matching
        Index('ix_ads_opdb_id', 'opdb_id'),

        # Index for retry management
        Index('ix_ads_retries_ignored', 'retries', 'ignored'),

        # Composite index for workflow status tracking
        Index('ix_ads_workflow_status', 'scraped_at', 'identified_at', 'ignored'),
    )

class Sub(Base):
    """SQLAlchemy model for subscriptions table."""

    __tablename__ = "subs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    opdb_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Define unique constraint on email + opdb_id combination
    __table_args__ = (
        UniqueConstraint('email', 'opdb_id', name='unique_email_opdb_id'),
    )


class Task(Base):
    """SQLAlchemy model for tasks table."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.IN_PROGRESS, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Define indexes for common query patterns
    __table_args__ = (
        # Index for filtering by name and created_at (to find latest task by name)
        Index('ix_tasks_name_created_at', 'name', 'created_at'),

        # Index for status filtering
        Index('ix_tasks_status', 'status'),
    )

