import click
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from pincrawl.database import Database, Watching, Ad, Task, TaskStatus, Product, Account
from pincrawl.task_manager import TaskManager
from pincrawl.smtp import Smtp
from pincrawl.email_utils import send_ad_notification_email
from pincrawl.graph_utils import generate_price_graph
import random

# Global configuration
SMTP_URL = os.getenv("SMTP_URL")
if not SMTP_URL:
    raise Exception("SMTP_URL environment variable not set")

FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@localhost")
PING_EMAIL = os.getenv("PING_EMAIL", None)

# Database and task manager instances
database = Database()
task_manager = TaskManager()

@click.group()
def watching():
    """Manage user watching list for pinball machines."""
    pass

@watching.command("list")
def watching_list():
    """List all current watching entries."""

    # Initialize database connection
    session = database.get_db()

    try:
        # Query all subscriptions ordered by email
        subscriptions = session.query(Watching).order_by(
            Watching.email,
            Watching.opdb_id
        ).all()

        if not subscriptions:
            click.echo("No watching entries found.")
            return

        # Display subscriptions in the requested format
        for subscription in subscriptions:
            click.echo(f"{subscription.email} {subscription.opdb_id}")

    except Exception as e:
        raise
    finally:
        session.close()


@watching.command("send")
def watching_send():
    """Send email notifications to watchers about new ads matching their watching list."""

    # Initialize database connection
    session = database.get_db()

    try:
        TASK_NAME = "watching-send"
        # Check the last task
        last_task = task_manager.get_latest_task_by_name(session, TASK_NAME)

        if last_task and last_task.status == TaskStatus.IN_PROGRESS:
            raise click.ClickException("✗ Previous task is still IN_PROGRESS. Exiting.")

        # Create a new task
        current_task = task_manager.create_task(session, TASK_NAME, TaskStatus.IN_PROGRESS)
        click.echo(f"✓ Created new task with ID {current_task.id}")

        try:
            # Find all ads that have been identified with an opdb_id since the last task
            if last_task:
                # Get ads identified since the last successful task
                new_ads = session.query(Ad).filter(
                    and_(
                        Ad.opdb_id.isnot(None),
                        Ad.identified_at >= last_task.created_at
                    )
                ).all()
            else:
                # If no previous task, get all identified ads
                new_ads = session.query(Ad).filter(
                    Ad.opdb_id.isnot(None)
                ).all()

            if not new_ads:
                click.echo("✓ No new ads found since last task")
                task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
                return

            click.echo(f"✓ Found {len(new_ads)} new ads with opdb_id")

            # Group subscriptions by email
            subscriptions_by_email = defaultdict(set)
            # Get unique opdb_ids from new ads
            new_opdb_ids = {ad.opdb_id for ad in new_ads if ad.opdb_id}
            # Only get subscriptions that match the opdb_ids from new ads
            relevant_subscriptions = session.query(Watching).filter(Watching.opdb_id.in_(new_opdb_ids)).all()

            for subscription in relevant_subscriptions:
                account = Account.get_by_id(session, subscription.account_id)
                if not account:
                    continue
                subscriptions_by_email[account.email].add(subscription.opdb_id)

            if not subscriptions_by_email:
                click.echo("✓ No subscriptions found")
                task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
                return

            # Group ads by email based on subscriptions
            email_to_ads = defaultdict(list)

            for ad in new_ads:
                for email, opdb_ids in subscriptions_by_email.items():
                    if ad.opdb_id in opdb_ids:
                        email_to_ads[email].append(ad)

            if not email_to_ads:
                click.echo("✓ No matching ads found for current subscriptions")
                task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
                return

            smtp_client = Smtp(SMTP_URL)

            # mail control
            # if this fails, we want to know before sending user emails
            if PING_EMAIL:
                smtp_client.send(FROM_EMAIL, PING_EMAIL, "pincrawl ping", "ping")
                click.echo(f"✓ Sent email control")

            email_count = 0
            for email, ads in email_to_ads.items():
                try:
                    # Get user's language preference from Account
                    account = session.query(Account).filter_by(email=email).first()

                    # Send email with HTML - pass Ad objects directly with locale
                    send_ad_notification_email(smtp_client, FROM_EMAIL, email, ads, locale=account.language)
                    email_count += 1
                    click.echo(f"✓ Sent email to {email} with {len(ads)} ads (locale: {account.language})")

                except Exception as e:
                    click.echo(f"❌ Failed to send email to {email}: {str(e)}")
                    logging.exception(f"Email error for {email}")
                    continue

            # Mark task as successful
            task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
            click.echo(f"✓ Task completed. Sent emails to {email_count} recipient(s)")



        except Exception as e:
            # Mark task as failed
            task_manager.update_task_status(session, current_task, TaskStatus.FAIL)
            raise

    finally:
        # Clean up old tasks, keeping only the last 100
        deleted_count = task_manager.cleanup_old_tasks(session)
        if deleted_count > 0:
            click.echo(f"✓ Cleaned up {deleted_count} old tasks")

        session.close()


@watching.command("test-email")
@click.argument("to")
@click.option("--locale", default="en", help="Language locale (en or fr)")
def test_email(to, locale):
    """Send a test email to verify SMTP configuration.

    Args:
        to: Email address to send the test email to
        locale: Language locale for the email (default: en)
    """

    smtp_client = Smtp(SMTP_URL)

    # Get base URL from environment variable
    PINCRAWL_BASE_URL = os.getenv('PINCRAWL_BASE_URL')
    if not PINCRAWL_BASE_URL:
        raise Exception("PINCRAWL_BASE_URL environment variable not set")

    # Generate a fake graph for testing


    # Generate fake data for the last year (12 months)
    current_date = datetime.now()
    dates = [current_date - timedelta(days=365-i*30) for i in range(12)]
    base_price = 8000
    variation = 1500
    prices = [base_price + random.randint(-variation//2, variation) for _ in range(12)]

    # Generate and save the graph (SVG format)
    graph_filepath = 'var/graphs/fake_data.png'
    generate_price_graph(dates, prices, f'www/{graph_filepath}', format='png')
    graph_url = f"{PINCRAWL_BASE_URL}/{graph_filepath}"

    graph_filepath = 'var/graphs/nodata.png'
    generate_price_graph(dates, prices, f'www/{graph_filepath}', format='png')
    nodata_graph_url = f"{PINCRAWL_BASE_URL}/{graph_filepath}"

    # Create fake ad data for testing
    fake_ads_data = [
        {
            'product': '[Fake] Medieval Madness',
            'manufacturer': 'Williams',
            'year': '1997',
            'url': 'https://example.com/ad/123',
            'price': 8500,
            'currency': 'EUR',
            'location': 'Paris, 75001',
            'graph_url': graph_url
        },
        {
            'product': '[Fake] Attack from Mars',
            'manufacturer': 'Bally',
            'year': '1995',
            'url': 'https://example.com/ad/456',
            'price': 7200,
            'currency': 'EUR',
            'location': 'Lyon, 69001',
            'graph_url': nodata_graph_url
        },
        {
            'product': '[Fake] The Addams Family',
            'manufacturer': 'Bally',
            'year': '1992',
            'url': 'https://example.com/ad/789',
            'price': 6500,
            'currency': 'EUR',
            'location': 'Marseille, 13001',
            'graph_url': nodata_graph_url
        }
    ]

    send_ad_notification_email(smtp_client, FROM_EMAIL, to, fake_ads_data, locale=locale)

    click.echo(f"✓ Test email sent successfully to {to} (locale: {locale})")





