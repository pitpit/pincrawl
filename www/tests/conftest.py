import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os
from pincrawl.database import Account, PlanType, Product

from main import app, db

from pincrawl.push_notification_service import NotSubscribedPushException


@pytest.fixture
def anonymous_client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def client(anonymous_client):
    """Create an authenticated test client with mocked session"""
    # Mock the get_authenticated_user dependency to return a user
    def mock_get_authenticated_user():
        return {'email': 'test@example.com', 'name': 'Test User'}

    # Override the dependency
    from main import get_authenticated_user
    app.dependency_overrides[get_authenticated_user] = mock_get_authenticated_user

    yield anonymous_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_session():
    """Mock database session"""
    session = MagicMock()
    with patch.object(db, 'get_db', return_value=session):
        yield session

@pytest.fixture
def mock_free_account(mock_session):
    """Mock account object"""

    account = MagicMock(spec=Account)
    account.id = 1
    account.email = 'test@example.com'
    account.language = 'en'
    account.email_notifications = True

    # Mock get_current_plan
    plan = MagicMock()
    plan.plan = PlanType.FREE
    plan.is_granted_for_push = MagicMock(return_value=False)
    account.get_current_plan = MagicMock(return_value=plan)

    Account.get_by_email = MagicMock(return_value=account)

    return account

@pytest.fixture
def mock_pro_account(mock_session):
    """Mock account object"""

    account = MagicMock(spec=Account)
    account.id = 2
    account.email = 'pro@example.com'
    account.language = 'en'
    account.email_notifications = True

    # Mock get_current_plan
    plan = MagicMock()
    plan.plan = PlanType.PRO
    plan.is_granted_for_push = MagicMock(return_value=True)
    account.get_current_plan = MagicMock(return_value=plan)

    Account.get_by_email = MagicMock(return_value=account)

    return account

@pytest.fixture
def mock_product(mock_session):
    """Mock product object"""

    product = MagicMock(spec=Product)
    product.id = 1
    product.opdb_id = 'test-opdb-id'

    return product

@pytest.fixture
def mock_push_service():
    with patch('main.PushNotificationService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_push_service_but_not_subscribed():
    with patch('main.PushNotificationService') as mock_service_class:
        mock_instance = MagicMock()

        mock_instance.send_notification.side_effect = NotSubscribedPushException("Send failed")

        mock_service_class.return_value = mock_instance
        yield mock_instance