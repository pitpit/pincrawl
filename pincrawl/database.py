"""Database configuration and models for PostgreSQL.

Usage:
    db = Database()
    session = db.get_db()
    # ... use session
    session.close()
    db.close_db()
"""

import os
from datetime import datetime
from typing import List, Optional, Union
from sqlalchemy import text, create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON, Index, UniqueConstraint, Enum, func, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import TSVECTOR
from dotenv import load_dotenv
import enum

# Module exports
__all__ = ['Database', 'Ad', 'Sub', 'Task', 'Product', 'Account', 'AccountHistory']

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

class PlanType(enum.Enum):
    """Enum for subscription plan types."""
    ALPHA = "ALPHA"
    FREE = "FREE"
    COLLECTOR = "COLLECTOR"
    PRO = "PRO"

# Plan limits for watching pinballs
PLAN_WATCHING_LIMITS = {
    PlanType.FREE: 3,
    PlanType.ALPHA: 10,
    PlanType.COLLECTOR: 10,
    PlanType.PRO: float('inf')  # Unlimited
}

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

    def _init_db(self) -> Engine:
        """Initialize database connection and create tables."""
        self.engine = create_engine(self.database_url)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Create tables
        Base.metadata.create_all(bind=self.engine)

        return self.engine

    def get_db(self) -> Session:
        """Get database session."""
        if self.session_local is None:
            self._init_db()

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
            self._init_db()

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
    content = Column(Text, nullable=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    amount = Column(Integer, nullable=True)  # Price amount in cents/smallest currency unit
    currency = Column(String, nullable=True)  # Currency code (EUR, USD, etc.)
    city = Column(String, nullable=True)  # City where the item is located
    zipcode = Column(String, nullable=True)  # Zipcode where the item is located
    seller = Column(String, nullable=True)  # Seller name or identifier
    seller_url = Column(String, nullable=True)  # Seller profile or contact URL
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

        # Index for seller searches
        Index('ix_ads_seller', 'seller'),

        # Index for seller URL searches
        Index('ix_ads_seller_url', 'seller_url'),

        # Composite index for workflow status tracking
        Index('ix_ads_workflow_status', 'scraped_at', 'identified_at', 'ignored'),
    )


    @staticmethod
    def fetch(session,
              scraped: Optional[bool] = None,
              identified: Optional[bool] = None,
              ignored: Optional[bool] = None,
              content: Optional[bool] = None) -> List["Ad"]:
        """
        Fetch ads from database with optional filtering.

        Args:
            scraped: Filter by scraped status (None=no filter, True=scraped, False=not scraped)
            identified: Filter by identified status (None=no filter, True=identified, False=not identified)
            ignored: Filter by ignored status (None=no filter, True=ignored, False=not ignored)
            content: Filter by content status (None=no filter, True=has content, False=no content)

        Returns:
            List of Ad objects matching the criteria
        """

        query = session.query(Ad)

        # Apply filters based on parameters
        if scraped is not None:
            if scraped:
                query = query.filter(Ad.scraped_at.isnot(None))
            else:
                query = query.filter(Ad.scraped_at.is_(None))

        if identified is not None:
            if identified:
                query = query.filter(Ad.product.isnot(None))
            else:
                query = query.filter(Ad.product.is_(None))

        if ignored is not None:
            query = query.filter(Ad.ignored == ignored)

        if content is not None:
            if content:
                query = query.filter(Ad.content.isnot(None))
            else:
                query = query.filter(Ad.content.is_(None))

        return query.all()

    @staticmethod
    def count(session,
              scraped: Optional[bool] = None,
              identified: Optional[bool] = None,
              ignored: Optional[bool] = None,
              content: Optional[bool] = None) -> int:
        """
        Count ads in database with optional filtering.

        Args:
            scraped: Filter by scraped status (None=no filter, True=scraped, False=not scraped)
            identified: Filter by identified status (None=no filter, True=identified, False=not identified)
            ignored: Filter by ignored status (None=no filter, True=ignored, False=not ignored)
            content: Filter by content status (None=no filter, True=has content, False=no content)

        Returns:
            Count of Ad objects matching the criteria
        """

        query = session.query(Ad)

        # Apply filters based on parameters (same logic as fetch method)
        if scraped is not None:
            if scraped:
                query = query.filter(Ad.scraped_at.isnot(None))
            else:
                query = query.filter(Ad.scraped_at.is_(None))

        if identified is not None:
            if identified:
                query = query.filter(Ad.product.isnot(None))
            else:
                query = query.filter(Ad.product.is_(None))

        if ignored is not None:
            query = query.filter(Ad.ignored == ignored)

        if content is not None:
            if content:
                query = query.filter(Ad.content.isnot(None))
            else:
                query = query.filter(Ad.content.is_(None))

        return query.count()

    @staticmethod
    def exists(session, url: str) -> bool:
        """
        Check if an ad with the given URL already exists in the database.

        Args:
            url: The URL to check for existence

        Returns:
            True if the ad exists, False otherwise
        """

        # Use EXISTS query for optimal performance
        exists_query = session.query(Ad).filter(Ad.url == url).exists()
        return session.query(exists_query).scalar()

    @staticmethod
    def store(session, ad_record: "Ad") -> "Ad":
        """
        Insert or update an Ad record in the database.

        Args:
            ad: The Ad object to store

        Returns:
            True if the operation was successful, False otherwise
        """

        if ad_record.url:
            # Check if ad already exists
            existing = session.query(Ad).filter(Ad.url == ad_record.url).first()

            if existing:
                # Update existing record
                for attr in ['content', 'title', 'description', 'amount', 'currency',
                            'city', 'zipcode', 'seller', 'seller_url', 'product', 'manufacturer', 'year',
                            'opdb_id', 'scraped_at', 'identified_at', 'scrape_id',
                            'ignored']:
                    if hasattr(ad_record, attr):
                        setattr(existing, attr, getattr(ad_record, attr))
            else:
                # Insert new record
                session.add(ad_record)
        else:
            # No URL, just insert
            session.add(ad_record)

        session.commit()

        return ad_record

    def price_graph_url(self, format: str = 'svg') -> str:
        """
        Generate graph URL for this ad based on its opdb_id.

        Returns:
            str: Graph URL
        """
        if not self.opdb_id:
            return ""

        if format not in ['svg', 'png']:
            format = 'svg'  # Default to svg for invalid formats

        return f"/graphs/{self.opdb_id}.{format}"


class Watching(Base):
    """SQLAlchemy model for watching table."""

    __tablename__ = "watching"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    opdb_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Relationship to account
    account = relationship("Account")

    @staticmethod
    def get_user_watching(session, account_id: int):
        """
        Get a set of opdb_ids that the user is watching.

        Args:
            account_id: Account ID watching

        Returns:
            set: Set of opdb_ids the user is watching
        """

        # Query user subscriptions
        items = session.query(Watching.opdb_id).filter(Watching.account_id == account_id).all()

        # Convert to set of opdb_ids
        opdb_ids = {item[0] for item in items if item[0]}

        return opdb_ids

    # Define unique constraint on account_id + opdb_id combination
    __table_args__ = (
        UniqueConstraint('account_id', 'opdb_id', name='unique_watching_account_opdb_id'),
        Index('ix_watching_account_id', 'account_id'),
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

class Product(Base):
    """SQLAlchemy model for products table."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    opdb_id = Column(String, unique=True, index=True, nullable=False)
    ipdb_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    shortname = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True, index=True)
    type = Column(String, nullable=True, index=True)
    year = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Full-text search vector
    search_vector = Column(TSVECTOR)

    # Define indexes for common query patterns
    __table_args__ = (
        # Index for product search queries
        Index('ix_products_name_manufacturer', 'name', 'manufacturer'),

        # Index for filtering by type and year
        Index('ix_products_type_year', 'type', 'year'),

        # Index for name-based searches (case insensitive searching)
        Index('ix_products_name_shortname', 'name', 'shortname'),

        # GIN index for full-text search
        Index('ix_products_search_vector', 'search_vector', postgresql_using='gin'),
    )


    @staticmethod
    def update_search_vectors(session):
        """Update search vectors for all products."""

        # Update search vectors using PostgreSQL's to_tsvector function
        update_query = text("""
            UPDATE products
            SET search_vector = to_tsvector('english',
                COALESCE(name, '') || ' ' ||
                COALESCE(shortname, '') || ' ' ||
                COALESCE(manufacturer, '')
            )
            WHERE search_vector IS NULL OR search_vector = ''
        """)
        session.execute(update_query)
        session.commit()

        # Get count of updated rows
        count_query = text("SELECT COUNT(*) FROM products WHERE search_vector IS NOT NULL")
        result = session.execute(count_query).scalar()

        return result

    @staticmethod
    def get_manufacturers(session):
        """
        Get a list of all unique manufacturers from the database.

        Args:
            session: Database session

        Returns:
            list: Sorted list of manufacturer names
        """

        # Query distinct manufacturers, excluding None/empty values
        manufacturers = session.query(Product.manufacturer).filter(
            Product.manufacturer.isnot(None),
            Product.manufacturer != ''
        ).distinct().order_by(Product.manufacturer).all()

        # Extract manufacturer names from tuples and filter out None values
        manufacturer_list = [mfg[0] for mfg in manufacturers if mfg[0]]

        return manufacturer_list

    @staticmethod
    def get_year_range(session):
        """
        Get the minimum and maximum years from the database.

        Args:
            session: Database session

        Returns:
            dict: Contains 'min_year' and 'max_year'
        """

        # Query min and max years, filtering out None/empty values and casting to integer
        result = session.query(
            func.min(Product.year.cast(Integer)).label('min_year'),
            func.max(Product.year.cast(Integer)).label('max_year')
        ).filter(
            Product.year.isnot(None),
            Product.year != '',
            Product.year.op('~')(r'^\d{4}$')  # Only 4-digit years
        ).first()

        min_year = result.min_year if result and result.min_year else 1930
        max_year = result.max_year if result and result.max_year else 2024

        return {'min_year': min_year, 'max_year': max_year}

    @staticmethod
    def fetch(session, query=None, manufacturer=None, year_min=None, year_max=None, subscribed_only_account_id=None, offset=0, limit=10):
        """
        List products from database or search using full-text index.

        Args:
            session: SQLAlchemy session
            query: Optional search query to filter products (uses full-text if provided)
            manufacturer: Optional manufacturer filter
            year_min: Optional minimum year filter
            year_max: Optional maximum year filter
            subscribed_only_account_id: Optional account ID for subscription filtering only
            offset: Number of products to skip (for pagination)
            limit: Maximum number of products to return

        Returns:
            dict: Contains 'products' list and 'total' count
        """
        db_query = session.query(Product)
        db_query = Product._apply_filters(db_query, manufacturer, year_min, year_max, subscribed_only_account_id)

        if query is not None and query.strip() != "":
            ts_query = func.plainto_tsquery('english', query)
            db_query = db_query.filter(Product.search_vector.op('@@')(ts_query))
            rank_score = func.ts_rank(Product.search_vector, ts_query).label('rank_score')
            db_query = session.query(Product, rank_score).filter(Product.search_vector.op('@@')(ts_query))
            db_query = Product._apply_filters(db_query, manufacturer, year_min, year_max, subscribed_only_account_id)
            db_query = db_query.order_by(rank_score.desc())
            total = db_query.count()
            results = db_query.offset(offset).limit(limit).all()
            products = [result[0] for result in results]
        else:
            total = db_query.count()
            db_query = db_query.order_by(Product.name)
            products = db_query.offset(offset).limit(limit).all()

        return products, total

    @staticmethod
    def _apply_filters(db_query, manufacturer=None, year_min=None, year_max=None, subscribed_only_account_id=None):
        """
        Apply manufacturer, year, and subscription filters to a database query.

        Args:
            db_query: SQLAlchemy query object
            manufacturer: Optional manufacturer filter
            year_min: Optional minimum year filter
            year_max: Optional maximum year filter
            subscribed_only_account_id: Optional account ID to show only subscribed products

        Returns:
            Modified query object with filters applied
        """
        if manufacturer is not None and manufacturer.strip() != "":
            db_query = db_query.filter(Product.manufacturer == manufacturer)
        if year_min is not None:
            try:
                year_min_int = int(year_min)
                db_query = db_query.filter(Product.year.cast(Integer) >= year_min_int)
            except (ValueError, TypeError):
                pass
        if year_max is not None:
            try:
                year_max_int = int(year_max)
                db_query = db_query.filter(Product.year.cast(Integer) <= year_max_int)
            except (ValueError, TypeError):
                pass
        if subscribed_only_account_id is not None:
            db_query = db_query.join(Watching, Product.opdb_id == Watching.opdb_id).filter(Watching.account_id == subscribed_only_account_id)

        return db_query

    @staticmethod
    def compute_price_statistics(session, save_to_db: bool = False) -> dict:
        """
        Compute monthly and yearly price statistics for all pinball machines.
        Note: save_to_db parameter is deprecated and has no effect.

        Args:
            session: Database session
            save_to_db: Deprecated - kept for backward compatibility

        Returns:
            dict: Statistics data with the following structure:
                {
                    'opdb_id': {
                        'machine_name': str,
                        'manufacturer': str,
                        'monthly_avg': int or None,
                        'yearly_avg': int or None,
                        'monthly_count': int,
                        'yearly_count': int
                    }
                }
        """
        from datetime import datetime, timedelta

        current_date = datetime.now()
        one_month_ago = current_date - timedelta(days=30)
        one_year_ago = current_date - timedelta(days=365)

        # Get the Ad class - it's defined in the same module
        import sys
        current_module = sys.modules[__name__]
        AdClass = getattr(current_module, 'Ad')

        # Query for monthly averages (last 30 days)
        monthly_query = session.query(
            AdClass.opdb_id,
            AdClass.product,
            AdClass.manufacturer,
            func.avg(AdClass.amount).label('avg_price'),
            func.count(AdClass.amount).label('count')
        ).filter(
            AdClass.opdb_id.isnot(None),
            AdClass.amount.isnot(None),
            AdClass.currency == 'EUR',  # Only EUR for consistency
            AdClass.ignored == False,
            AdClass.created_at >= one_month_ago
        ).group_by(AdClass.opdb_id, AdClass.product, AdClass.manufacturer)

        # Query for yearly averages (last 365 days)
        yearly_query = session.query(
            AdClass.opdb_id,
            AdClass.product,
            AdClass.manufacturer,
            func.avg(AdClass.amount).label('avg_price'),
            func.count(AdClass.amount).label('count')
        ).filter(
            AdClass.opdb_id.isnot(None),
            AdClass.amount.isnot(None),
            AdClass.currency == 'EUR',  # Only EUR for consistency
            AdClass.ignored == False,
            AdClass.created_at >= one_year_ago
        ).group_by(AdClass.opdb_id, AdClass.product, AdClass.manufacturer)

        monthly_results = monthly_query.all()
        yearly_results = yearly_query.all()

        # Create dictionaries for lookups
        monthly_stats = {result.opdb_id: result for result in monthly_results}
        yearly_stats = {result.opdb_id: result for result in yearly_results}

        # Get all unique pinball machines from both queries
        all_opdb_ids = set(monthly_stats.keys()) | set(yearly_stats.keys())

        # Build statistics dictionary
        statistics = {}

        for opdb_id in all_opdb_ids:
            monthly_data = monthly_stats.get(opdb_id)
            yearly_data = yearly_stats.get(opdb_id)

            # Get machine name from either monthly or yearly data
            machine_name = (monthly_data.product if monthly_data else yearly_data.product) or "Unknown"
            manufacturer = (monthly_data.manufacturer if monthly_data else yearly_data.manufacturer) or "Unknown"

            # Calculate averages
            monthly_avg = int(monthly_data.avg_price) if monthly_data else None
            yearly_avg = int(yearly_data.avg_price) if yearly_data else None

            monthly_count = monthly_data.count if monthly_data else 0
            yearly_count = yearly_data.count if yearly_data else 0

            statistics[opdb_id] = {
                'machine_name': machine_name,
                'manufacturer': manufacturer,
                'monthly_avg': monthly_avg,
                'yearly_avg': yearly_avg,
                'monthly_count': monthly_count,
                'yearly_count': yearly_count
            }

        # Add metadata to the result
        return {
            'statistics': statistics,
            'total_machines': len(all_opdb_ids),
            'updated_count': 0,  # No longer saves to DB
            'saved_to_db': False
        }

    def price_graph_url(self, format: str = 'svg') -> str:
        """
        Generate price graph URL for this product.

        Args:
            format: Output format ('svg' or 'png'), defaults to 'svg'

        Returns:
            str: Graph URL for this product
        """
        if format not in ['svg', 'png']:
            format = 'svg'  # Default to svg for invalid formats
        return f"/graphs/{self.opdb_id}.{format}"

class Account(Base):
    """SQLAlchemy model for accounts table."""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    language = Column(String(2), nullable=True, default=None)  # ISO 639-1 language code for communication (email, SMS, WhatsApp) - does not affect UI navigation
    push_subscription = Column(JSON, nullable=True)  # Web Push subscription data
    email_notifications = Column(Boolean, nullable=True, default=True)  # Email notifications preference
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Relationship to account history
    history = relationship("AccountHistory", back_populates="account", cascade="all, delete-orphan")

    # Define indexes for common query patterns
    __table_args__ = (
        # Index for email lookups (already created by unique=True and index=True)
        # Index for created_at sorting
        Index('ix_accounts_created_at', 'created_at'),
    )

    @staticmethod
    def create_account(session, email: str, language: Optional[str] = None) -> "Account":
        """
        Create a new account with automatic free plan history entry.

        Args:
            session: Database session
            email: Account email address
            language: Optional preferred language code for communication (e.g., 'en', 'fr')

        Returns:
            Account: The created account object
        """
        # Create the account
        account = Account(email=email, language=language)
        session.add(account)
        session.flush()  # Flush to get the account ID

        # Create the initial free plan history entry
        history_entry = AccountHistory(
            account_id=account.id,
            plan=PlanType.FREE,
            start_date=datetime.now()
        )
        session.add(history_entry)
        session.commit()

        return account

    @staticmethod
    def get_by_email(session, email: str) -> Optional["Account"]:
        """
        Get account by email address.

        Args:
            session: Database session
            email: Account email address

        Returns:
            Account or None if not found
        """
        return session.query(Account).filter(Account.email == email).first()

    @staticmethod
    def get_by_id(session, account_id: int) -> Optional["Account"]:
        """
        Get account by ID.

        Args:
            session: Database session
            account_id: Account ID

        Returns:
            Account or None if not found
        """
        return session.query(Account).filter(Account.id == account_id).first()

    def get_current_plan(self, session) -> Optional["AccountHistory"]:
        """
        Get the current active plan for this account.

        Args:
            session: Database session

        Returns:
            AccountHistory: Current plan or None if no active plan
        """
        return session.query(AccountHistory).filter(
            AccountHistory.account_id == self.id,
            AccountHistory.end_date.is_(None)
        ).first()

    @property
    def push_notifications(self) -> bool:
        """
        Check if push notifications are enabled for this account.

        Returns:
            bool: True if push notifications are enabled
        """
        return self.push_subscription is not None and bool(self.push_subscription)

class AccountHistory(Base):
    """SQLAlchemy model for account_history table."""

    __tablename__ = "account_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    plan = Column(Enum(PlanType), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)  # NULL means current active plan

    # Relationship to account
    account = relationship("Account", back_populates="history")

    # Define indexes for common query patterns
    __table_args__ = (
        # Index for finding active plans (end_date IS NULL)
        Index('ix_account_history_account_active', 'account_id', 'end_date'),

        # Index for plan type filtering
        Index('ix_account_history_plan', 'plan'),

        # Index for date range queries
        Index('ix_account_history_dates', 'start_date', 'end_date'),
    )

    @staticmethod
    def change_plan(session, account_id: int, new_plan: PlanType) -> "AccountHistory":
        """
        Change account plan by ending current plan and starting new one.

        Args:
            session: Database session
            account_id: Account ID
            new_plan: New plan type

        Returns:
            AccountHistory: The new plan history entry
        """
        current_time = datetime.now()

        # End the current active plan
        current_plan = session.query(AccountHistory).filter(
            AccountHistory.account_id == account_id,
            AccountHistory.end_date.is_(None)
        ).first()

        if current_plan:
            current_plan.end_date = current_time

        # Create new plan entry
        new_plan_entry = AccountHistory(
            account_id=account_id,
            plan=new_plan,
            start_date=current_time
        )
        session.add(new_plan_entry)
        session.commit()

        return new_plan_entry


    def is_granted_for_push(self) -> bool:
        """
        Check if the account's current plan allows push notifications.

        Args:
            session: Database session
        Returns:
            bool: True if push notifications are allowed
        """
        # Check if user has PRO plan
        if (self.plan != PlanType.PRO):
            return False

        return True