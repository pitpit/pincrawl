#!/usr/bin/env python3
"""Migration to add push_emails column to accounts table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add push_emails column to accounts table."""
    db = Database()
    session = db.get_db()

    try:
        # Add push_emails column to accounts table (Boolean type with default TRUE)
        session.execute(text("""
            ALTER TABLE accounts ADD COLUMN IF NOT EXISTS push_emails BOOLEAN DEFAULT TRUE;
        """))

        session.commit()
        print("✓ Successfully added 'push_emails' column to accounts table")

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
