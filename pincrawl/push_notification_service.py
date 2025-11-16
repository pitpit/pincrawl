"""Web Push notification service for sending alerts to users."""

import json
import os
import logging
from typing import Optional, Dict, Any
from pincrawl.database import Ad, Account
from pincrawl.i18n import I18n
from typing import List
import onesignal
from onesignal.api import default_api
from onesignal.model.notification import Notification
# from onesignal.model.rate_limit_error import RateLimitError
# from onesignal.model.generic_error import GenericError
# from onesignal.model.create_notification_success_response import CreateNotificationSuccessResponse

logger = logging.getLogger(__name__)

ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY")
if not ONESIGNAL_API_KEY:
    raise Exception("ONESIGNAL_API_KEY environment variable is not set.")

ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
if not ONESIGNAL_APP_ID:
    raise Exception("ONESIGNAL_APP_ID environment variable is not set.")

class NotSubscribedPushException(Exception):
    """Exception raised when trying to send push notification to user who is not subscribed."""
    pass

class PushNotificationService:
    """Service for sending Web Push notifications."""

    def __init__(self, i18n: I18n):
        """
        Initialize push notification service.

        Args:
            i18n: Internationalization service for localized messages
        """
        self.i18n = i18n

        configuration = onesignal.Configuration(
            rest_api_key = ONESIGNAL_API_KEY,
        )

        api_client = onesignal.ApiClient(configuration)
        self.api_instance = default_api.DefaultApi(api_client)


    def send_notification(self, remote_ids: list[str], title: str, body: str, url: str):
        """
        Send a push notification to a subscriber.

        Args:
            remote_ids: List of OneSignal remote IDs
            title: Notification title
            body: Notification body text
            url: URL to open when notification is clicked

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            notification = Notification(
                app_id=ONESIGNAL_APP_ID,
                headings={"en": title},
                contents={"en": body},
                url=url,
                include_aliases= { "external_id": remote_ids },
                target_channel="push"
            )

            logger.debug(f"notification: {notification}")

            api_response = self.api_instance.create_notification(notification)

            logger.debug(f"OneSignal API response: {api_response}")

            if "errors" in api_response and api_response.errors:

                invalid_aliases = []

                if isinstance(api_response.errors, dict):
                    for error_type, error_data in api_response.errors.items():
                        if "invalid_aliases" == error_type:
                            invalid_aliases = error_data
                        else:
                            raise Exception(f"Push notification error: {api_response.errors}")
                elif isinstance(api_response.errors, list):
                    for error_data in api_response.errors:
                        if "All included players are not subscribed" == error_data:
                            invalid_aliases = remote_ids
                        else:
                            raise Exception(f"Push notification error: {api_response.errors}")

                if invalid_aliases:
                    raise NotSubscribedPushException(f"Invalid push subscription for remote IDs: {invalid_aliases}")

            logger.info(f"Push notification sent successfully to remote IDs: {remote_ids}")

        except Exception as e:
            raise

    def send_ad_notification_push(self, account: Account, ad: Ad):
        """
        Send push notifications for new ads to a user account.

        Args:
            account: Account object with push subscription data
            ads: List of Ad objects from database

        Returns:
            int: Number of push notifications sent successfully

        Raises:
            Exception: If account doesn't have push enabled or subscription data is invalid
        """

        i18n_context = self.i18n.create_context(account.language)

        title = i18n_context._("New pinball machine found!")
        body = f"{ad.product}"
        if ad.manufacturer:
            body += f", {ad.manufacturer}"
        if ad.year:
            body += f", {ad.year}"
        if ad.amount and ad.currency:
            body += "\n" + i18n_context._('Price: %s %s') % (ad.amount, ad.currency)
        if ad.city:
            body += "\n" + i18n_context._('Location: %s') % (ad.city)
            if ad.zipcode:
                body += f", {ad.zipcode}"

        # Send push notification
        self.send_notification(
            remote_ids=[str(account.remote_id)],
            title=title,
            body=body,
            url=ad.url
        )
