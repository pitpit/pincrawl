#!/usr/bin/env python3
"""
Database migration script to:
Remove old price statistics columns (monthly_price_average, yearly_price_average, monthly_ads_count, yearly_ads_count)

Note: Graph filenames are now deterministic based on opdb_id, so no database field is needed.
"""

import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_migration():
    """Migrate database schema for graph-based price statistics."""
    try:
        from pincrawl.database import Database

        db = Database()
        session = db.get_db()

        print("Running database migration for graph-based price statistics...")

        # Check existing columns
        check_columns_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'products'
            AND column_name IN ('monthly_price_average', 'yearly_price_average',
                                'monthly_ads_count', 'yearly_ads_count')
        """)

        existing_columns = session.execute(check_columns_query).fetchall()
        existing_column_names = [row[0] for row in existing_columns]

        migrations_needed = []

        # Remove old columns if they exist
        columns_to_remove = ['monthly_price_average', 'yearly_price_average',
                            'monthly_ads_count', 'yearly_ads_count']

        for column in columns_to_remove:
            if column in existing_column_names:
                migrations_needed.append(f"ALTER TABLE products DROP COLUMN {column}")
                print(f"  → Will remove {column} column")

        if not migrations_needed:
            print("✓ Database schema is already up to date")
            session.close()
            return True

        # Run migrations
        for migration in migrations_needed:
            print(f"Executing: {migration}")
            session.execute(text(migration))

        session.commit()
        session.close()

        print(f"✓ Migration completed successfully. Executed {len(migrations_needed)} operation(s).")
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
    print("Next steps:")
    print("  1. Run 'pincrawl ads generate-graph' to create price timeline graphs")
    print("  2. Generated graphs will be saved to www/static/img/graphs/")
