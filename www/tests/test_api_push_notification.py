import pytest
from unittest.mock import MagicMock, patch
from pincrawl.database import Account


class TestTestPushNotificationAPI:
    """Tests for /api/test-push-notification endpoint"""

    def test_requires_authentication(self, anonymous_client):
        """Test that endpoint requires authentication"""
        response = anonymous_client.post("/api/test-push-notification")
        assert response.status_code == 401

    @patch('main.PushNotificationService')
    def test_send_test_notification_success(self, mock_push_service, mock_pro_account, mock_session, client):
        """Test sending test push notification"""

        mock_pro_account.push_notifications = True
        mock_pro_account.push_subscription = {"endpoint": "https://example.com"}

        response = client.post("/api/test-push-notification")

        assert response.status_code == 200
        assert response.json() == {'success': True}
        # mock_push_service.send_push_notification.assert_called_once()

    @patch('main.PushNotificationService')
    def test_no_push_subscription(self, mock_push_service, mock_pro_account, mock_session, client):
        """Test error when no push subscription exists"""

        mock_pro_account.push_notifications = True
        mock_pro_account.push_subscription = None

        response = client.post("/api/test-push-notification")

        assert response.status_code == 400
        mock_push_service.send_push_notification.assert_not_called()

    @patch('main.PushNotificationService')
    def test_push_notifications_not_enabled(self, mock_push_service, mock_pro_account, mock_session, client):
        """Test error when push notifications are not enabled"""

        mock_pro_account.push_notifications = False
        mock_pro_account.push_subscription = {"endpoint": "https://example.com"}

        response = client.post("/api/test-push-notification")

        assert response.status_code == 400
        mock_push_service.send_push_notification.assert_not_called()

    @patch('main.PushNotificationService')
    def test_plan_does_not_allow_push(self, mock_push_service, mock_free_account, mock_session, client):
        """Test error when plan doesn't allow push notifications"""

        mock_free_account.push_notifications = True
        mock_free_account.push_subscription = {"endpoint": "https://example.com"}

        response = client.post("/api/test-push-notification")

        assert response.status_code == 402
        mock_push_service.send_push_notification.assert_not_called()
