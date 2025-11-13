#!/usr/bin/env python3
"""Migration to populate the previous field in ads table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Populate previous_id field by linking ads to their previous versions."""
    db = Database()
    session = db.get_db()

    try:
        # Update previous_id field to point to the most recent prior ad
        # that shares the same seller_url and opdb_id
        session.execute(text("""
            UPDATE ads a
            SET previous_id = (
                SELECT id
                FROM ads prev
                WHERE
                    -- Match seller_url (both not null and equal)
                    (a.seller_url IS NOT NULL AND prev.seller_url = a.seller_url)
                    -- Match opdb_id (both not null and equal)
                    AND (a.opdb_id IS NOT NULL AND prev.opdb_id = a.opdb_id)
                    -- Previous ad must have been created before this one
                    AND prev.created_at < a.created_at
                    -- Exclude self-reference
                    AND prev.id != a.id
                ORDER BY prev.created_at DESC
                LIMIT 1
            )
            WHERE a.seller_url IS NOT NULL AND a.opdb_id IS NOT NULL
        """))

        result = session.execute(text("SELECT COUNT(*) FROM ads WHERE previous_id IS NOT NULL")).scalar()
        session.commit()
        print(f"✓ Successfully populated 'previous_id' field. {result} ads now have a previous reference.")

    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
