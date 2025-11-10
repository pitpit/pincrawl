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

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """Service for sending email notifications with ad data."""

    def __init__(self, smtp_client):
        """Initialize email notification service."""
        self.smtp_client = smtp_client

        # Create i18n instance
        self.i18n = I18n(files('pincrawl').joinpath('translations'))

        # Get base URL from environment variable
        self.base_url = os.getenv('PINCRAWL_BASE_URL')
        if not self.base_url:
            raise Exception("PINCRAWL_BASE_URL environment variable not set")

        # Get BCC recipient from environment variable
        self.bcc_email = os.getenv('BCC_EMAIL', None)

        # Initialize database connection
        self.db = Database()

    def send_ad_notification_email(self, from_email, to_email, ads, locale=None):
        """
        Send an email notification with ad data using HTML template.

        Args:
            from_email: Sender email address
            to_email: Recipient email address
            ads: List of Ad objects from database or list of dictionaries with ad data
            locale: str (optional) - Language code ('en', 'fr')

        Returns:
            None

        Raises:
            Exception: If template cannot be loaded or email fails to send
        """
        # Get database session to look up product IDs
        session = self.db.get_db()

        try:
            # Prepare ads data for template
            ads_data = []
            for ad in ads:
                # Check if it's an Ad object or a dictionary
                if hasattr(ad, 'product'):
                    # It's an Ad object from database
                    ad_info = {
                        'product': ad.product or 'Unknown',
                        'manufacturer': ad.manufacturer,
                        'year': ad.year,
                        'url': ad.url,
                        'price': ad.amount,
                        'currency': ad.currency,
                        'location': None,
                        'graph_url': None
                    }

                    # Format location
                    if ad.city:
                        location_parts = [ad.city]
                        if ad.zipcode:
                            location_parts.append(ad.zipcode)
                        ad_info['location'] = ', '.join(location_parts)

                    # Set graph URL if available - look up product_id from opdb_id
                    if ad.opdb_id:
                        product = session.query(Product).filter_by(opdb_id=ad.opdb_id).first()
                        if product:
                            # Use the dynamic graph endpoint with product_id (PNG for better email client support)
                            ad_info['graph_url'] = f"{self.base_url}/graphs/{product.id}.png"
                else:
                    # It's already a dictionary (for testing)
                    ad_info = ad

                ads_data.append(ad_info)
        finally:
            session.close()

        # Load email template using importlib.resources for proper package data access
        template_file = files('pincrawl').joinpath('templates', 'email_notification.html')
        template_content = template_file.read_text()

        i18n_context = self.i18n.create_context(locale)

        template = Template(template_content)
        html_body = template.render(
            ads_count=len(ads_data),
            ads=ads_data,
            base_url=self.base_url,
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
        self.smtp_client.send(from_email, to_email, subject, html_body, html=True, bcc=self.bcc_email)


# Legacy function for backward compatibility
def send_ad_notification_email(smtp_client, from_email, to_email, ads, locale=None):
    """
    Legacy function for backward compatibility.

    Deprecated: Use EmailNotificationService.send_ad_notification_email() instead.
    """
    service = EmailNotificationService(smtp_client)
    return service.send_ad_notification_email(from_email, to_email, ads, locale)
