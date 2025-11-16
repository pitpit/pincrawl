#!/usr/bin/env python3
"""Migration to add remote_id UUID column to accounts table."""

from sqlalchemy import text
from pincrawl.database import Database

def migrate():
    """Add remote_id UUID column to accounts table and populate it for existing users."""
    db = Database()
    session = db.get_db()

    try:
        # Add the column as nullable first
        session.execute(text("""
            ALTER TABLE accounts
            ADD COLUMN IF NOT EXISTS remote_id UUID;
        """))

        # Populate existing records with UUIDs
        session.execute(text("""
            UPDATE accounts
            SET remote_id = gen_random_uuid()
            WHERE remote_id IS NULL;
        """))

        # Make the column non-nullable
        session.execute(text("""
            ALTER TABLE accounts
            ALTER COLUMN remote_id SET NOT NULL;
        """))

        # Add unique constraint
        session.execute(text("""
            ALTER TABLE accounts
            ADD CONSTRAINT uq_accounts_remote_id UNIQUE (remote_id);
        """))

        # Create index
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_accounts_remote_id
            ON accounts (remote_id);
        """))

        session.commit()
        print("✓ Successfully added 'remote_id' column to accounts table and populated it for existing users")
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate()
