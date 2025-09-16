#!/usr/bin/env python3

import click
import logging
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from pincrawl.database import Database, Sub

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Database instance
database = Database()

@click.group()
def subs():
    """Manage user subscriptions to pinball machines."""
    pass

@subs.command("add")
@click.argument("email")
@click.argument("opdb_id")
def subs_add(email, opdb_id):
    """Add a new subscription for a user to a specific pinball machine.

    Args:
        email: User's email address
        opdb_id: OPDB ID of the pinball machine
    """
    try:
        # Initialize database connection
        database.init_db()
        session = database.get_db()

        try:
            # Check if subscription already exists
            existing = session.query(Sub).filter_by(
                email=email,
                opdb_id=opdb_id
            ).first()

            if existing:
                click.echo(f"✓ User {email} is already subscribed to {opdb_id}")
                return

            # Create new subscription
            subscription = Sub(email=email, opdb_id=opdb_id)
            session.add(subscription)
            session.commit()

            click.echo(f"✓ Added subscription: {email} -> {opdb_id}")

        except IntegrityError:
            session.rollback()
            click.echo(f"✓ User {email} is already subscribed to {opdb_id}")
        except Exception as e:
            session.rollback()
            raise click.ClickException(f"Failed to add subscription: {str(e)}")
        finally:
            session.close()

    except Exception as e:
        raise click.ClickException(f"Database error: {str(e)}")

@subs.command("list")
def subscriptions_list():
    """List all current subscriptions."""
    try:
        # Initialize database connection
        database.init_db()
        session = database.get_db()

        try:
            # Query all subscriptions ordered by email
            subscriptions = session.query(Sub).order_by(
                Sub.email,
                Sub.opdb_id
            ).all()

            if not subscriptions:
                click.echo("No subscriptions found.")
                return

            # Display subscriptions in the requested format
            for subscription in subscriptions:
                click.echo(f"{subscription.email} {subscription.opdb_id}")

        except Exception as e:
            raise click.ClickException(f"Failed to list subscriptions: {str(e)}")
        finally:
            session.close()

    except Exception as e:
        raise click.ClickException(f"Database error: {str(e)}")