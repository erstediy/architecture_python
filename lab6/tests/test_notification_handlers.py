import pytest
from unittest.mock import patch
from services.notification_service.main import HANDLERS


def test_status_changed_handler_called():
    payload = {"id": 1, "old_status": "active", "new_status": "sold"}
    with patch("services.notification_service.main.log") as mock_log:
        HANDLERS["property.status_changed"](payload)
        mock_log.info.assert_called_once()
        args = mock_log.info.call_args[0]
        assert 1 in args
        assert "active" in args
        assert "sold" in args


def test_viewing_scheduled_handler_called():
    payload = {"id": 10, "property_id": 1, "buyer_id": 99, "scheduled_at": "2025-06-15T10:00:00"}
    with patch("services.notification_service.main.log") as mock_log:
        HANDLERS["viewing.scheduled"](payload)
        mock_log.info.assert_called_once()
        args = mock_log.info.call_args[0]
        assert 10 in args
        assert 1 in args
        assert 99 in args


def test_no_handler_for_property_created():
    assert "property.created" not in HANDLERS


def test_no_handler_for_user_created():
    assert "user.created" not in HANDLERS
