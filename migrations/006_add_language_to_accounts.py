#!/usr/bin/env python3
"""Migration to add language column to accounts table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add language column to accounts table."""
    db = Database()
    session = db.get_db()

    try:
        # Add language column (nullable, default NULL)
        session.execute(text("""
            ALTER TABLE accounts
            ADD COLUMN IF NOT EXISTS language VARCHAR(2) DEFAULT NULL
        """))

        # Set language to 'fr' for all existing users
        session.execute(text("""
            UPDATE accounts
            SET language = 'fr'
            WHERE language IS NULL
        """))

        session.commit()
        print("✓ Successfully added language column to accounts table")
        print("✓ Set language to 'fr' for all existing users")

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
