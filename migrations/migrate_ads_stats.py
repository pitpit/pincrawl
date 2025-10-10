#!/usr/bin/env python3
"""
Database migration script to add monthly_price_average and yearly_price_average columns to the products table.
This script should be run once to update the database schema.
"""

import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pincrawl'))

def run_migration():
    """Add the new columns to the products table if they don't exist."""
    try:
        from pincrawl.database import Database

        db = Database()
        session = db.get_db()

        print("Running database migration for ads stats feature...")

        # Check if columns already exist
        check_columns_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'products'
            AND column_name IN ('monthly_price_average', 'yearly_price_average')
        """)

        existing_columns = session.execute(check_columns_query).fetchall()
        existing_column_names = [row[0] for row in existing_columns]

        migrations_needed = []

        if 'monthly_price_average' not in existing_column_names:
            migrations_needed.append("ALTER TABLE products ADD COLUMN monthly_price_average INTEGER")

        if 'yearly_price_average' not in existing_column_names:
            migrations_needed.append("ALTER TABLE products ADD COLUMN yearly_price_average INTEGER")

        if not migrations_needed:
            print("✓ Database schema is already up to date")
            return True

        # Run migrations
        for migration in migrations_needed:
            print(f"Executing: {migration}")
            session.execute(text(migration))

        session.commit()
        session.close()

        print(f"✓ Migration completed successfully. Added {len(migrations_needed)} column(s).")
        return True

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return False

if __name__ == "__main__":
    success = run_migration()
    if not success:
        sys.exit(1)

    print("\n🎉 Database migration completed!")