"""
Email utility functions for sending notifications with ads data.
"""
import logging
import os
from pathlib import Path
from jinja2 import Template
from pincrawl.database import Database, Product
from pincrawl.i18n import I18n
from importlib.resources import files
from pincrawl.database import Ad, Account
from typing import List


# Get base URL from environment variable
PINCRAWL_BASE_URL = os.getenv('PINCRAWL_BASE_URL')
if not PINCRAWL_BASE_URL:
    raise Exception("PINCRAWL_BASE_URL environment variable not set")

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """Service for sending email notifications with ad data."""

    def __init__(self, smtp_client):
        """Initialize email notification service."""
        self.smtp_client = smtp_client

        # Create i18n instance
        self.i18n = I18n(files('pincrawl').joinpath('translations'))

        # Get BCC recipient from environment variable
        self.bcc_email = os.getenv('BCC_EMAIL', None)

        # Initialize database connection
        self.db = Database()

    def send_ad_notification_email(self, from_email, account: Account, ads: List[Ad], locale=None):
        """
        Send an email notification with ad data using HTML template.

        Args:
            from_email: Sender email address
            account: Account object for the recipient
            ads: List of Ad objects from database
            locale: str (optional) - Language code ('en', 'fr')

        Returns:
            None

        Raises:
            Exception: If template cannot be loaded or email fails to send
        """

        # Load email template using importlib.resources for proper package data access
        template_file = files('pincrawl').joinpath('templates', 'email_notification.html')
        template_content = template_file.read_text()

        i18n_context = self.i18n.create_context(locale)

        template = Template(template_content)
        html_body = template.render(
            ads=ads,
            base_url=PINCRAWL_BASE_URL,
            _=i18n_context._,
            locale=i18n_context.locale
        )

        subject = i18n_context._('New pinball machines found')

        # For debugging: save rendered HTML to file
        # TODO comment
        debug_html_path = 'www/static/test_email.html'
        with open(debug_html_path, 'w') as f:
            f.write(html_body)

        # Send email with HTML
        self.smtp_client.send(from_email, account.email, subject, html_body, html=True, bcc=self.bcc_email)
