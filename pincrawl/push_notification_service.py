"""Web Push notification service for sending alerts to users."""

import json
import logging
from typing import Optional, Dict, Any
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

class PushNotificationService:
    """Service for sending Web Push notifications."""

    def __init__(self, vapid_private_key: str, vapid_claims: Dict[str, str]):
        """
        Initialize push notification service.

        Args:
            vapid_private_key: VAPID private key for authentication
            vapid_claims: VAPID claims including 'sub' (contact email)
        """
        self.vapid_private_key = vapid_private_key
        self.vapid_claims = vapid_claims

    def send_notification(self, subscription: Dict[str, Any], title: str, body: str, url: str) -> bool:
        """
        Send a push notification to a subscriber.

        Args:
            subscription: Push subscription data from browser
            title: Notification title
            body: Notification body text
            url: URL to open when notification is clicked

        Returns:
            bool: True if notification was sent successfully
        """
        try:
            payload = {
                'title': title,
                'body': body,
                'url': url
            }

            webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )

            logger.info(f"Push notification sent successfully to endpoint: {subscription.get('endpoint', 'unknown')}")
            return True

        except WebPushException as e:
            if e.response and e.response.status_code == 410:
                # Subscription is no longer valid
                logger.warning(f"Push subscription expired: {subscription.get('endpoint', 'unknown')}")
            else:
                logger.error(f"Failed to send push notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending push notification: {e}")
            return False

    def send_ad_notification_push(self, account, ads):
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
        if not account.has_push_enabled():
            raise Exception(f"Push notifications not enabled for account {account.email}")

        push_count = 0

        try:
            for ad in ads:
                title = "New pinball machine found!"
                body = f"{ad.product}"
                if ad.manufacturer:
                    body += f", {ad.manufacturer}"
                if ad.year:
                    body += f", {ad.year}"
                if ad.amount and ad.currency:
                    body += f"\nPrice: {ad.amount} {ad.currency}"
                if ad.city:
                    body += f"\nLocation: {ad.city}"
                    if ad.zipcode:
                        body += f", {ad.zipcode}"

                # Send push notification
                success = self.send_notification(
                    subscription=account.push_subscription,
                    title=title,
                    body=body,
                    url=ad.url
                )

                if success:
                    push_count += 1
                    logger.info(f"Sent push notification to account {account.email} for ad {ad.url}")
                else:
                    logger.error(f"Failed to send push notification to account {account.email} for ad {ad.url}")

        except Exception as e:
            logger.error(f"Error sending push notifications to account {account.email}: {e}")
            raise

        return push_count
