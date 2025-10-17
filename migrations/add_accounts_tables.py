#!/usr/bin/env python3
"""
Migration script to add the new accounts and account_history tables.

Usage:
    python migrations/add_accounts_tables.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pincrawl.database import Database, Account, AccountHistory

def migrate_add_accounts_tables():
    """Create the new accounts and account_history tables."""

    print("Creating new accounts and account_history tables...")

    # Initialize database
    db = Database()
    session = db.get_db()

    try:
        # Create tables (this will only create tables that don't exist)
        db._init_db()
        print("✓ Tables created successfully")

        # Check if tables were created by counting rows
        account_count = session.query(Account).count()
        history_count = session.query(AccountHistory).count()

        print(f"✓ Accounts table: {account_count} rows")
        print(f"✓ Account history table: {history_count} rows")

        print("\n🎉 Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()
        db.close_db()

if __name__ == "__main__":
    migrate_add_accounts_tables()