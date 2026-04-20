import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_pool():
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_process_property_created(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()

    with patch("services.query_service.main.pool", pool):
        from services.query_service.main import _process_event
        await _process_event({
            "event_type": "property.created",
            "payload": {
                "id": 1, "owner_id": 42, "title": "Test", "type": "apartment",
                "city": "Москва", "address": "ул. Ленина, 1",
                "price": 5000000.0, "area": 50.0, "rooms": 2,
                "status": "active", "created_at": "2025-01-01T00:00:00",
            },
        })
    conn.execute.assert_called_once()
    call_sql = conn.execute.call_args[0][0]
    assert "INSERT INTO properties_read" in call_sql
    assert "ON CONFLICT" in call_sql


@pytest.mark.asyncio
async def test_process_property_status_changed(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()

    with patch("services.query_service.main.pool", pool):
        from services.query_service.main import _process_event
        await _process_event({
            "event_type": "property.status_changed",
            "payload": {"id": 1, "owner_id": 42, "old_status": "active", "new_status": "sold"},
        })
    conn.execute.assert_called_once()
    call_sql = conn.execute.call_args[0][0]
    assert "UPDATE properties_read" in call_sql


@pytest.mark.asyncio
async def test_process_viewing_scheduled(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()

    with patch("services.query_service.main.pool", pool):
        from services.query_service.main import _process_event
        await _process_event({
            "event_type": "viewing.scheduled",
            "payload": {
                "id": 10, "property_id": 1, "buyer_id": 99,
                "scheduled_at": "2025-06-15T10:00:00",
            },
        })
    conn.execute.assert_called_once()
    call_sql = conn.execute.call_args[0][0]
    assert "INSERT INTO viewings_read" in call_sql


@pytest.mark.asyncio
async def test_process_unknown_event(mock_pool):
    pool, conn = mock_pool
    conn.execute = AsyncMock()

    with patch("services.query_service.main.pool", pool):
        from services.query_service.main import _process_event
        await _process_event({"event_type": "unknown.event", "payload": {}})
    conn.execute.assert_not_called()
