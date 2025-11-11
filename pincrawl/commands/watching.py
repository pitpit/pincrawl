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
                if account.push_emails:
                    try:
                        email_notification_service.send_ad_notification_email(FROM_EMAIL, account, ads, locale=account.language)
                        email_count += 1
                        logging.info(f"Sent email to {account.email} with {len(ads)} ads (locale: {account.language})")
                    except Exception as e:
                        logging.exception(f"Failed to send email to {account.email}")
                else:
                    logging.info(f"Email notifications disabled for account {account.email}")

                # Send push notifications if enabled and service is available
                if account.push_notifications:
                    current_plan = account.get_current_plan(session)
                    if (current_plan and current_plan.is_granted_for_push()):
                        try:
                            for ad in ads:
                                push_notification_service.send_ad_notification_push(account, ad)
                                push_count += 1
                            logging.info(f"Sent 1 push notification to account {account.email}")
                        except Exception as e:
                            logging.exception(f"Failed to send 1 push notification to account {account.email}")
                    else:
                        logging.info(f"Push notifications not allowed for account {account.email} due to plan restrictions")
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
@click.argument("email")
@click.option("--locale", default="en", help="Language locale (en or fr)")
def test_email(email, locale):
    """Send a test email to verify SMTP configuration.

    Args:
        email: Email address to send the test email to
        locale: Language locale for the email (default: en)
    """

    session = database.get_db()

    account = session.query(Account).filter(Account.email == email).first()
    if not account:
        raise click.ClickException(f"Account with email {email} not found")

    if not account.push_emails:
        raise click.ClickException(f"Email notifications not enabled for account {email}")

    smtp_client = Smtp(SMTP_URL)
    email_notification_service = EmailNotificationService(smtp_client)

    fake_ads = get_fake_ads()

    email_notification_service.send_ad_notification_email(FROM_EMAIL, account, fake_ads, locale=locale)

    click.echo(f"✓ Test email sent successfully to {email} (locale: {locale})")


@watching.command("test-push")
@click.argument("email")
def test_push(email):
    """Send a test push notification to verify push configuration.

    Args:
        email: Email address of the account to send the test notification to
    """

    session = database.get_db()

    # Find account by email
    account = session.query(Account).filter(Account.email == email).first()
    if not account:
        raise click.ClickException(f"Account with email {email} not found")

    if not account.push_notifications:
        raise click.ClickException(f"Push notifications not enabled for account {email}")

    current_plan = account.get_current_plan(session)
    if not current_plan or not current_plan.is_granted_for_push():
        raise click.ClickException(f"Push notifications not allowed for account {email} due to plan restrictions")

    # Initialize push notification service
    vapid_claims = {'sub': f'mailto:{VAPID_CONTACT_EMAIL}'}
    push_notification_service = PushNotificationService(VAPID_PRIVATE_KEY, vapid_claims)

    # Create fake ad data for testing using real Ad entities
    fake_ads = get_fake_ads()

    # Send test push notifications
    push_count = 0
    for ad in fake_ads:
        push_notification_service.send_ad_notification_push(account, ad)
        push_count += 1

    click.echo(f"✓ {push_count} notifications sent successfully to {email}")


def get_fake_ads():

    # Create fake ad data for testing using real Ad entities
    fake_ads = [
        Ad(
            product="[Fake] Medieval Madness",
            manufacturer="Williams",
            opdb_id="G5pe4-MePZv",
            year="1997",
            amount=8500,
            currency="EUR",
            city="Paris",
            zipcode="75001",
            url="https://example.com/test-ad/123"
        ),
        Ad(
            product="[Fake] Attack from Mars",
            manufacturer="Bally",
            opdb_id="G4do5-MDlN7",
            year="1995",
            amount=7200,
            currency="EUR",
            city="Lyon",
            zipcode="69001",
            url="https://example.com/test-ad/456"
        )
    ]
    return fake_ads



