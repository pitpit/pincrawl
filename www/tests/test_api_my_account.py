import pytest
from unittest.mock import MagicMock, patch
from pincrawl.database import Account


class TestMyAccountAPI:
    """Tests for /api/my-account endpoint"""

    def test_update_account_requires_authentication(self, anonymous_client):
        """Test that endpoint requires authentication"""
        response = anonymous_client.put("/api/my-account", json={"language": "fr"})
        assert response.status_code == 401

    def test_update_language_success(self, mock_free_account, mock_session, client):
        """Test updating language preference"""

        response = client.put("/api/my-account", json={"language": "fr"})

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert mock_free_account.language == 'fr'

    def test_update_language_invalid(self, mock_free_account, mock_session, client):
        """Test updating to invalid language"""

        response = client.put("/api/my-account", json={"language": "invalid"})

        assert response.status_code == 400

    def test_update_email_notifications(self, mock_free_account, mock_session, client):
        """Test updating email notification preference"""

        response = client.put("/api/my-account", json={"email_notifications": False})

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert mock_free_account.email_notifications == False

    def test_update_email_notifications(self, mock_free_account, mock_session, client):
        """Test updating email notification preference"""

        response = client.put("/api/my-account", json={"email_notifications": False})

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert mock_free_account.email_notifications == False

    def test_subscribe_push_without_plan(self, mock_free_account, mock_session, client):
        """Test subscribing to push notifications without proper plan"""

        push_data = {"endpoint": "https://example.com", "keys": {}}

        response = client.put("/api/my-account", json={"push_subscription": push_data})

        assert response.status_code == 402

    def test_subscribe_push_without_pro_plan(self, mock_pro_account, mock_session, client):
        """Test subscribing to push notifications without proper plan"""

        push_data = {"endpoint": "https://example.com", "keys": {}}

        response = client.put("/api/my-account", json={"push_subscription": push_data})

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert mock_pro_account.push_subscription == push_data

    def test_unsubscribe_push(self, mock_pro_account, mock_session, client):
        """Test unsubscribing from push notifications"""

        response = client.put("/api/my-account", json={"push_subscription": None})

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert mock_pro_account.push_subscription is None

    def test_unsubscribe_push_without_plan(self, mock_free_account, mock_session, client):
        """Test unsubscribing from push notifications"""

        response = client.put("/api/my-account", json={"push_subscription": None})

        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert mock_free_account.push_subscription is None