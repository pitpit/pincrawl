#!/usr/bin/env python3
"""Migration to add seller_url column to ads table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add seller_url column to ads table."""
    db = Database()
    session = db.get_db()

    try:
        # Add seller_url column to ads table
        session.execute(text("""
            ALTER TABLE ads ADD COLUMN IF NOT EXISTS seller_url VARCHAR;
        """))

        # Add index on seller_url column for search performance
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_ads_seller_url ON ads (seller_url);
        """))

        session.commit()
        print("✓ Successfully added 'seller_url' column and index to ads table")

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()