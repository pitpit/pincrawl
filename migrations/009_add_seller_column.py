#!/usr/bin/env python3
"""Migration to add seller column and index to ads table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add seller column and index to ads table."""
    db = Database()
    session = db.get_db()

    try:
        # Add seller column to ads table
        session.execute(text("""
            ALTER TABLE ads ADD COLUMN IF NOT EXISTS seller VARCHAR;
        """))
        
        # Add index on seller column for search performance
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_ads_seller ON ads (seller);
        """))
        
        session.commit()
        print("✓ Successfully added 'seller' column and index to ads table")

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
