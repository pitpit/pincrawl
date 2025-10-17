#!/usr/bin/env python3
"""
Migration script to rename the 'subs' table to 'watching'.

Usage:
    python migrations/rename_subs_to_watching.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pincrawl.database import Database
from sqlalchemy import text

def migrate_rename_subs_to_watching():
    """Rename the 'subs' table to 'watching'."""
    try:
        print("Starting migration to rename 'subs' table to 'watching'...")

        db = Database()
        session = db.get_db()

        # Check if 'subs' table exists
        check_subs_table = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'subs'
        """)

        subs_exists = session.execute(check_subs_table).fetchone()

        if not subs_exists:
            print("✓ Table 'subs' does not exist, nothing to migrate")
            return True

        # Rename the table
        rename_table = text("DROP TABLE IF EXISTS watching; ALTER TABLE subs RENAME TO watching")
        session.execute(rename_table)
        session.commit()

        print("✓ Successfully renamed table 'subs' to 'watching'")

        # Update the unique constraint name if it exists
        try:
            update_constraint = text("""
                ALTER TABLE watching
                RENAME CONSTRAINT unique_email_opdb_id
                TO unique_watching_email_opdb_id
            """)
            session.execute(update_constraint)
            session.commit()
            print("✓ Successfully renamed unique constraint")
        except Exception as e:
            print(f"⚠ Warning: Could not rename constraint (this may be normal): {e}")

        return True

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        session.rollback()
        return False

    finally:
        session.close()

if __name__ == "__main__":
    success = migrate_rename_subs_to_watching()
    if success:
        print("✓ Migration completed successfully")
        sys.exit(0)
    else:
        print("✗ Migration failed")
        sys.exit(1)