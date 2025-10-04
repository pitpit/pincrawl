import click
import os
from datetime import datetime
from pincrawl.smtp import Smtp

# Global configuration
SMTP_URL = os.getenv("SMTP_URL")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@localhost")


@click.group()
def mailer():
    """Manage email-related tasks."""
    pass

@mailer.command("test")
@click.argument("to")
def mailer_test(to):
    """Send a test email to verify SMTP configuration.

    Args:
        email: Email address to send the test email to
    """

    if not SMTP_URL:
        raise Exception("SMTP_URL environment variable not set")

    smtp_client = Smtp(SMTP_URL)

    # Create test email content
    subject = "PinCrawl Email Test"
    body = f"""Hello,

This is a test email from PinCrawl to verify that email functionality is working correctly.

If you received this email, the SMTP configuration is working properly.

Test details:
- Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- From: {FROM_EMAIL}
- To: {to}

Best regards,
PinCrawl Team"""

    # Send test email
    smtp_client.send(FROM_EMAIL, to, subject, body)
    click.echo(f"✓ Test email sent successfully to {to}")

