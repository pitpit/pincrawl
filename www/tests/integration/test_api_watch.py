import pytest
from unittest.mock import MagicMock, patch
from pincrawl.database import Account, Watching, Product, PlanType


class TestWatchAPI:
    """Tests for /api/watch endpoint"""

    def test_requires_authentication(self, anonymous_client):
        """Test that endpoint requires authentication"""
        response = anonymous_client.post("/api/watch", json={"id": 1})
        assert response.status_code == 401

    def test_missing_id_parameter(self, client):
        """Test error when id parameter is missing"""

        response = client.post("/api/watch", json={})

        assert response.status_code == 400

    def test_watch_product_success(self, mock_product, mock_free_account, mock_session, client):
        """Test adding a watch subscription"""

        # Mock that product exists
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_product

        # Mock that no existing subscription exists
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [mock_product, None]

        # Mock watching count query
        mock_session.query.return_value.filter_by.return_value.count.return_value = 0

        response = client.post("/api/watch", json={"id": 1})

        assert response.status_code == 201
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_unwatch_product_success(self, mock_product, mock_free_account, mock_session, client):
        """Test removing a watch subscription"""

        mock_existing = MagicMock()

        # Mock that product exists
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [mock_product, mock_existing]

        response = client.post("/api/watch", json={"id": 1})

        assert response.status_code == 202
        mock_session.delete.assert_called_once_with(mock_existing)
        mock_session.commit.assert_called_once()

    def test_watch_product_not_found(self, mock_free_account, mock_session, client):
        """Test watching non-existent product"""

        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        response = client.post("/api/watch", json={"id": 999})

        assert response.status_code == 404

    def test_watch_limit_reached(self, mock_product, mock_free_account, mock_session, client):
        """Test watching when limit is reached"""

        # Mock existing subscription check returns None (no existing subscription)
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [mock_product, None]

        # Mock watching count at limit (3 for FREE plan)
        mock_session.query.return_value.filter_by.return_value.count.return_value = 3

        response = client.post("/api/watch", json={"id": 1})

        assert response.status_code == 402

    def test_no_account_found(self, mock_session, client):
        """Test error when user account is not found"""

        Account.get_by_email = MagicMock(return_value=None)

        response = client.post("/api/watch", json={"id": 1})

        assert response.status_code == 400
