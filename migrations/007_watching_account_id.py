"""
Migration: Convert Watching table from email to account_id foreign key

This migration:
1. Adds account_id column to watching table
2. Populates account_id from email by looking up accounts
3. Removes email column
4. Updates constraints and indexes

Run with: python -m migrations.001_watching_account_id
"""

import sys
import os
from sqlalchemy import text, MetaData, Table, Column, Integer, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.exc import IntegrityError

# Add parent directory to path to import pincrawl
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pincrawl.database import Database, Account

def upgrade(db: Database):
    """Apply the migration"""
    session = db.get_db()

    try:
        print("Starting migration: watching email -> account_id")

        # Step 1: Add account_id column (nullable for now)
        print("Step 1: Adding account_id column...")
        session.execute(text("""
            ALTER TABLE watching
            ADD COLUMN account_id INTEGER
        """))
        session.commit()
        print("✓ Added account_id column")

        # Step 2: Populate account_id from email
        print("Step 2: Populating account_id from email...")
        watching_records = session.execute(text("""
            SELECT id, email FROM watching
        """)).fetchall()

        updated_count = 0
        orphaned_count = 0

        for record_id, email in watching_records:
            # Look up account by email
            account = Account.get_by_email(session, email)

            if account:
                session.execute(text("""
                    UPDATE watching
                    SET account_id = :account_id
                    WHERE id = :record_id
                """), {"account_id": account.id, "record_id": record_id})
                updated_count += 1
            else:
                print(f"  ⚠ Warning: No account found for email '{email}', record id={record_id}")
                orphaned_count += 1

        session.commit()
        print(f"✓ Updated {updated_count} records")

        if orphaned_count > 0:
            print(f"⚠ Warning: {orphaned_count} orphaned records (no matching account)")
            print("  These records will be deleted in the next step")

            # Delete orphaned records
            session.execute(text("""
                DELETE FROM watching WHERE account_id IS NULL
            """))
            session.commit()
            print(f"✓ Deleted {orphaned_count} orphaned records")

        # Step 3: Make account_id NOT NULL and add foreign key
        print("Step 3: Adding NOT NULL constraint and foreign key...")
        session.execute(text("""
            ALTER TABLE watching
            ALTER COLUMN account_id SET NOT NULL
        """))
        session.execute(text("""
            ALTER TABLE watching
            ADD CONSTRAINT watching_account_id_fkey
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        """))
        session.commit()
        print("✓ Added constraints")

        # Step 4: Drop old unique constraint
        print("Step 4: Dropping old unique constraint...")
        session.execute(text("""
            ALTER TABLE watching
            DROP CONSTRAINT IF EXISTS unique_watching_email_opdb_id
        """))
        session.commit()
        print("✓ Dropped old constraint")

        # Step 5: Add new unique constraint on account_id + opdb_id
        print("Step 5: Adding new unique constraint...")
        session.execute(text("""
            ALTER TABLE watching
            ADD CONSTRAINT unique_watching_account_opdb_id
            UNIQUE (account_id, opdb_id)
        """))
        session.commit()
        print("✓ Added new constraint")

        # Step 6: Add index on account_id
        print("Step 6: Adding index on account_id...")
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_watching_account_id
            ON watching (account_id)
        """))
        session.commit()
        print("✓ Added index")

        # Step 7: Drop email column
        print("Step 7: Dropping email column...")
        session.execute(text("""
            ALTER TABLE watching DROP COLUMN email
        """))
        session.commit()
        print("✓ Dropped email column")

        print("\n✅ Migration completed successfully!")
        print(f"   - Updated {updated_count} watching records")
        print(f"   - Deleted {orphaned_count} orphaned records")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        raise
    finally:
        session.close()


def downgrade(db: Database):
    """Rollback the migration"""
    session = db.get_db()

    try:
        print("Starting rollback: watching account_id -> email")

        # Step 1: Add email column back
        print("Step 1: Adding email column...")
        session.execute(text("""
            ALTER TABLE watching
            ADD COLUMN email VARCHAR
        """))
        session.commit()
        print("✓ Added email column")

        # Step 2: Populate email from account_id
        print("Step 2: Populating email from account_id...")
        watching_records = session.execute(text("""
            SELECT w.id, w.account_id, a.email
            FROM watching w
            JOIN accounts a ON w.account_id = a.id
        """)).fetchall()

        for record_id, account_id, email in watching_records:
            session.execute(text("""
                UPDATE watching
                SET email = :email
                WHERE id = :record_id
            """), {"email": email, "record_id": record_id})

        session.commit()
        print(f"✓ Updated {len(watching_records)} records")

        # Step 3: Make email NOT NULL
        print("Step 3: Adding NOT NULL constraint on email...")
        session.execute(text("""
            ALTER TABLE watching
            ALTER COLUMN email SET NOT NULL
        """))
        session.commit()
        print("✓ Added constraint")

        # Step 4: Drop new unique constraint
        print("Step 4: Dropping new unique constraint...")
        session.execute(text("""
            ALTER TABLE watching
            DROP CONSTRAINT IF EXISTS unique_watching_account_opdb_id
        """))
        session.commit()
        print("✓ Dropped constraint")

        # Step 5: Add old unique constraint
        print("Step 5: Adding old unique constraint...")
        session.execute(text("""
            ALTER TABLE watching
            ADD CONSTRAINT unique_watching_email_opdb_id
            UNIQUE (email, opdb_id)
        """))
        session.commit()
        print("✓ Added old constraint")

        # Step 6: Drop index on account_id
        print("Step 6: Dropping index on account_id...")
        session.execute(text("""
            DROP INDEX IF EXISTS ix_watching_account_id
        """))
        session.commit()
        print("✓ Dropped index")

        # Step 7: Drop foreign key and account_id column
        print("Step 7: Dropping foreign key and account_id column...")
        session.execute(text("""
            ALTER TABLE watching
            DROP CONSTRAINT IF EXISTS watching_account_id_fkey
        """))
        session.execute(text("""
            ALTER TABLE watching
            DROP COLUMN account_id
        """))
        session.commit()
        print("✓ Dropped foreign key and column")

        print("\n✅ Rollback completed successfully!")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Rollback failed: {str(e)}")
        raise
    finally:
        session.close()


def main():
    """Run the migration"""
    import argparse

    parser = argparse.ArgumentParser(description='Migrate Watching table to use account_id')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    db = Database()

    try:
        if args.rollback:
            downgrade(db)
        else:
            upgrade(db)
    finally:
        db.close_db()


if __name__ == '__main__':
    main()
