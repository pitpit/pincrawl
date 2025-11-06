"""
Email utility functions for sending notifications with ads data.
"""
import logging
import os
from pathlib import Path
from jinja2 import Template


def send_ad_notification_email(smtp_client, from_email, to_email, ads, subject=None):
    """
    Send an email notification with ad data using HTML template.

    Args:
        smtp_client: Instance of Smtp client
        from_email: Sender email address
        to_email: Recipient email address
        ads: List of Ad objects from database or list of dictionaries with ad data
        subject: str (optional) - Email subject, defaults to auto-generated

    Returns:
        None

    Raises:
        Exception: If template cannot be loaded or email fails to send
    """
    # Get base URL from environment variable
    PINCRAWL_BASE_URL = os.getenv('PINCRAWL_BASE_URL')
    if not PINCRAWL_BASE_URL:
        raise Exception("PINCRAWL_BASE_URL environment variable not set")

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

            # Set graph URL if available
            if ad.opdb_id:
                graph_path = Path(f"www/static/img/graphs/{ad.opdb_id}.svg")
                if graph_path.exists():
                    ad_info['graph_url'] = f"{PINCRAWL_BASE_URL}/static/img/graphs/{ad.opdb_id}.svg"
        else:
            # It's already a dictionary (for testing)
            ad_info = ad

        ads_data.append(ad_info)

    # Load email template
    template_path = Path(__file__).parent / 'templates' / 'email_notification.html'
    with open(template_path, 'r') as f:
        template_content = f.read()

    template = Template(template_content)
    html_body = template.render(
        ads_count=len(ads_data),
        ads=ads_data,
        base_url=PINCRAWL_BASE_URL
    )

    # Create email subject if not provided
    if subject is None:
        subject = f"New pinball machines found - {len(ads_data)} match{'es' if len(ads_data) != 1 else ''}"


    # For debugging: save rendered HTML to file
    # TODO comment
    debug_html_path = 'www/static/test_email.html'
    with open(debug_html_path, 'w') as f:
        f.write(html_body)

    # Send email with HTML
    smtp_client.send(from_email, to_email, subject, html_body, html=True)
