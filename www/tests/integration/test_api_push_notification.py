import pytest
from unittest.mock import MagicMock, patch
from pincrawl.database import Account
from pincrawl.push_notification_service import NotSubscribedPushException


class TestTestPushNotificationAPI:
    """Tests for /api/test-push-notification endpoint"""

    def test_requires_authentication(self, anonymous_client):
        """Test that endpoint requires authentication"""
        response = anonymous_client.post("/api/test-push-notification")
        assert response.status_code == 401

    def test_send_test_notification_success(self, mock_push_service, mock_pro_account, mock_session, client):
        """Test sending test push notification"""

        response = client.post("/api/test-push-notification")

        assert response.status_code == 200
        assert response.json() == {'success': True}
        mock_push_service.send_notification.assert_called_once()

    @patch('main.PushNotificationService')
    def test_no_push_subscription(self, patched_push_service, mock_pro_account, mock_session, client):
        """Test error when no push subscription exists"""

        mock_push_service = MagicMock()
        mock_push_service.send_notification.side_effect = NotSubscribedPushException("Send failed")
        patched_push_service.return_value = mock_push_service

        response = client.post("/api/test-push-notification")

        assert response.status_code == 400
        mock_push_service.send_notification.assert_called_once()

    def test_plan_does_not_allow_push(self, mock_push_service, mock_free_account, mock_session, client):
        """Test error when plan doesn't allow push notifications"""

        response = client.post("/api/test-push-notification")

        assert response.status_code == 402
        mock_push_service.send_notification.assert_not_called()
