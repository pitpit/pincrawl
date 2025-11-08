#!/usr/bin/env python3
"""Migration to add language column to accounts table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add language column to accounts table."""
    db = Database()
    session = db.get_db()

    try:
        # Replace 'NEW_PLAN_TYPE' with the actual enum value you added to PlanType
        # For example: 'ENTERPRISE', 'PREMIUM', etc.
        session.execute(text("""
            ALTER TYPE plantype ADD VALUE IF NOT EXISTS 'ALPHA';
        """))
        session.commit()
        print("✓ Successfully added 'ALPHA' to PlanType enum")

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
