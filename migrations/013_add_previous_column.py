#!/usr/bin/env python3
"""Migration to add previous column to ads table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add previous_id column to ads table."""
    db = Database()
    session = db.get_db()

    try:
        # Add previous_id column to ads table
        session.execute(text("""
            ALTER TABLE ads ADD COLUMN IF NOT EXISTS previous_id INTEGER;
        """))

        # Add foreign key constraint
        session.execute(text("""
            ALTER TABLE ads
            ADD CONSTRAINT fk_ads_previous_id
            FOREIGN KEY (previous_id) REFERENCES ads(id);
        """))

        # Add index on previous_id column for query performance
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_ads_previous_id ON ads (previous_id);
        """))

        session.commit()
        print("✓ Successfully added 'previous_id' column, foreign key, and index to ads table")
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
