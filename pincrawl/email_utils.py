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

# Create i18n instance
i18n = I18n(files('pincrawl').joinpath('translations'))

def send_ad_notification_email(smtp_client, from_email, to_email, ads, locale=None):
    """
    Send an email notification with ad data using HTML template.

    Args:
        smtp_client: Instance of Smtp client
        from_email: Sender email address
        to_email: Recipient email address
        ads: List of Ad objects from database or list of dictionaries with ad data
        subject: str (optional) - Email subject, defaults to auto-generated
        locale: str (optional) - Language code ('en', 'fr')

    Returns:
        None

    Raises:
        Exception: If template cannot be loaded or email fails to send
    """

    # Get base URL from environment variable
    PINCRAWL_BASE_URL = os.getenv('PINCRAWL_BASE_URL')
    if not PINCRAWL_BASE_URL:
        raise Exception("PINCRAWL_BASE_URL environment variable not set")

    # Get database session to look up product IDs
    db = Database()
    session = db.get_db()

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
                        ad_info['graph_url'] = f"{PINCRAWL_BASE_URL}/graphs/{product.id}.png"
            else:
                # It's already a dictionary (for testing)
                ad_info = ad

            ads_data.append(ad_info)
    finally:
        session.close()

    # Load email template using importlib.resources for proper package data access
    template_file = files('pincrawl').joinpath('templates', 'email_notification.html')
    template_content = template_file.read_text()

    i18n_context = i18n.create_context(locale)

    template = Template(template_content)
    html_body = template.render(
        ads_count=len(ads_data),
        ads=ads_data,
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
    smtp_client.send(from_email, to_email, subject, html_body, html=True)
