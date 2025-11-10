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
from pincrawl.email_notification_service import EmailNotificationService
from pincrawl.graph_utils import generate_price_graph
from pincrawl.push_notification_service import PushNotificationService
import random

# Global configuration
SMTP_URL = os.getenv("SMTP_URL")
if not SMTP_URL:
    raise Exception("SMTP_URL environment variable not set")

FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@localhost")
PING_EMAIL = os.getenv("PING_EMAIL", None)

# Push notification configuration
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')
if not VAPID_PRIVATE_KEY:
    raise Exception("VAPID_PRIVATE_KEY environment variable not set")
VAPID_CONTACT_EMAIL = os.getenv('VAPID_CONTACT_EMAIL', 'pincrawl@pitp.it')

# Database and task manager instances
database = Database()
task_manager = TaskManager()

def format_price(amount: int, currency: str) -> str:
    """Format price for display."""
    if currency == 'EUR':
        return f"€{amount / 100:.2f}"
    elif currency == 'USD':
        return f"${amount / 100:.2f}"
    else:
        return f"{amount / 100:.2f} {currency}"

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
    """Send email and push notifications to watchers about new ads matching their watching list."""

    # Initialize database connection
    session = database.get_db()

    # Initialize services
    vapid_claims = {'sub': f'mailto:{VAPID_CONTACT_EMAIL}'}
    push_notification_service = PushNotificationService(VAPID_PRIVATE_KEY, vapid_claims)

    try:
        TASK_NAME = "watching-send"
        # Check the last task
        last_task = task_manager.get_latest_task_by_name(session, TASK_NAME)

        if last_task and last_task.status == TaskStatus.IN_PROGRESS:
            raise click.ClickException("✗ Previous notification task is still IN_PROGRESS. Exiting.")

        # Create a new task
        current_task = task_manager.create_task(session, TASK_NAME, TaskStatus.IN_PROGRESS)
        logging.info(f"Created new notification task with ID {current_task.id}")

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
                click.echo("✓ No new ads found since last notification task")
                task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
                return

            logging.info(f"Found {len(new_ads)} new ads with opdb_id")

            # Group subscriptions by account
            # Get unique opdb_ids from new ads
            new_opdb_ids = {ad.opdb_id for ad in new_ads if ad.opdb_id}
            # Only get subscriptions that match the opdb_ids from new ads
            relevant_subscriptions = session.query(Watching).filter(Watching.opdb_id.in_(new_opdb_ids)).all()

            if not relevant_subscriptions:
                click.echo("✓ No subscriptions found")
                task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
                return

            # Group ads by account based on subscriptions
            account_to_ads = defaultdict(list)

            for subscription in relevant_subscriptions:
                for ad in new_ads:
                    if ad.opdb_id == subscription.opdb_id:
                        account_to_ads[subscription.account_id].append(ad)

            smtp_client = Smtp(SMTP_URL)
            email_notification_service = EmailNotificationService(smtp_client)

            # mail control
            # if this fails, we want to know before sending user emails
            if PING_EMAIL:
                smtp_client.send(FROM_EMAIL, PING_EMAIL, "pincrawl ping", "ping")
                logging.info("Sent email control")

            email_count = 0
            push_count = 0

            for account_id, ads in account_to_ads.items():
                # Get account details
                account = Account.get_by_id(session, account_id)
                if not account:
                    logging.warning(f"Account ID {account_id} not found. Skipping.")
                    continue

                # Send email notification
                try:
                    email_notification_service.send_ad_notification_email(FROM_EMAIL, account.email, ads, locale=account.language)
                    email_count += 1
                    logging.info(f"Sent email to {account.email} with {len(ads)} ads (locale: {account.language})")
                except Exception as e:
                    logging.exception(f"Failed to send email to {account.email}")

                # Send push notifications if enabled and service is available
                if account.has_push_enabled():
                    try:
                        notifications_sent = push_notification_service.send_ad_notification_push(account, ads)
                        push_count += notifications_sent
                        logging.info(f"Sent {notifications_sent} push notifications to account {account.email}")
                    except Exception as e:
                        logging.exception(f"Failed to send push notifications to account {account.email}")
                else:
                    logging.info(f"Push notifications disabled for account {account.email}")

            # Mark task as successful
            task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
            click.echo(f"✓ Notification task completed. Sent {email_count} emails and {push_count} push notifications")

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
    email_notification_service = EmailNotificationService(smtp_client)

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

    email_notification_service.send_ad_notification_email(FROM_EMAIL, to, fake_ads_data, locale=locale)

    click.echo(f"✓ Test email sent successfully to {to} (locale: {locale})")





