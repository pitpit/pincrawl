#!/usr/bin/env python3
"""Migration to refactor push subscriptions."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Remove push_subscription from accounts."""
    db = Database()
    session = db.get_db()

    try:
        # Remove push_subscription column from accounts table
        session.execute(text("""
            ALTER TABLE accounts DROP COLUMN IF EXISTS push_subscription;
        """))

        session.commit()
        print("✓ Successfully removed 'push_subscription' column from accounts")
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
