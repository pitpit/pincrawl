import click
import logging
import os
from collections import defaultdict
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from pincrawl.database import Database, Sub, Ad, Task, TaskStatus
from pincrawl.task_manager import TaskManager
from pincrawl.smtp import Smtp


# Global configuration
SMTP_URL = os.getenv("SMTP_URL")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@localhost")


logger = logging.getLogger(__name__)

# Database and task manager instances
database = Database()
task_manager = TaskManager()

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
    # Initialize database connection
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
        raise
    finally:
        session.close()

@subs.command("list")
def subscriptions_list():
    """List all current subscriptions."""

    # Initialize database connection
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
        raise
    finally:
        session.close()


@subs.command("send")
def subs_send():
    """Send email notifications to subscribers about new ads matching their subscriptions."""

    # Initialize database connection
    session = database.get_db()

    try:
        TASK_NAME = "subs-send"
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
            relevant_subscriptions = session.query(Sub).filter(Sub.opdb_id.in_(new_opdb_ids)).all()

            for subscription in relevant_subscriptions:
                subscriptions_by_email[subscription.email].add(subscription.opdb_id)

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

            if not SMTP_URL:
                raise Exception("SMTP_URL environment variable not set")

            smtp_client = Smtp(SMTP_URL)

            for email, ads in email_to_ads.items():
                try:
                    # Create email content
                    subject = f"New pinball machines found - {len(ads)} match{'es' if len(ads) == 1 else ''}"

                    body = "Hello,\n\n"
                    body += f"We found {len(ads)} new pinball machine{'s' if len(ads) != 1 else ''} matching your subscriptions:\n\n"

                    for ad in ads:
                        body += f"• {ad.product}, {ad.manufacturer}, {ad.year}\n"
                        body += f"  URL: {ad.url}\n"
                        if ad.amount and ad.currency:
                            body += f"  Price: {ad.amount} {ad.currency}\n"
                        if ad.city:
                            body += f"  Location: {ad.city},  {ad.zipcode}\n"
                        body += "\n"

                    body += "Best regards,\nPincrawl Team"

                    # Send email
                    smtp_client.send(FROM_EMAIL, email, subject, body)
                    click.echo(f"✓ Sent email to {email} with {len(ads)} ads")

                except Exception as e:
                    logger.error(f"Failed to send email to {email}: {str(e)}")
                    click.echo(f"❌ Failed to send email to {email}: {str(e)}")

            # Mark task as successful
            task_manager.update_task_status(session, current_task, TaskStatus.SUCCESS)
            click.echo(f"✓ Task completed successfully. Sent emails to {len(email_to_ads)} recipient(s)")

        except Exception as e:
            # Mark task as failed
            task_manager.update_task_status(session, current_task, TaskStatus.FAIL)
            logger.error(f"Task failed: {str(e)}")
            raise

    finally:
        session.close()
