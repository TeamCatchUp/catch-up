import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.chat.background_runner import get_background_runner
from catchup.chat.dependencies import get_valid_chat_room
from catchup.chat.event_store import get_event_store
from catchup.server.chat.api import router


def _build_app(*, runner, event_store) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_valid_chat_room] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_background_runner] = lambda: runner
    app.dependency_overrides[get_event_store] = lambda: event_store
    return app


def test_status_not_generating_skips_redis() -> None:
    runner = MagicMock()
    runner.is_running = MagicMock(return_value=False)
    event_store = MagicMock()
    event_store.get_tail_id = AsyncMock()

    app = _build_app(runner=runner, event_store=event_store)
    session_id = uuid.uuid4()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/chat/{session_id}/status")

    assert response.status_code == 200
    assert response.json() == {"is_generating": False, "cutoff_id": None}
    assert response.headers["cache-control"] == "no-store"
    event_store.get_tail_id.assert_not_called()


def test_status_generating_returns_cutoff() -> None:
    runner = MagicMock()
    runner.is_running = MagicMock(return_value=True)
    event_store = MagicMock()
    event_store.get_tail_id = AsyncMock(return_value=("10-0", False))

    app = _build_app(runner=runner, event_store=event_store)
    session_id = uuid.uuid4()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/chat/{session_id}/status")

    assert response.status_code == 200
    assert response.json() == {"is_generating": True, "cutoff_id": "10-0"}


def test_status_race_done_seen_overrides_to_not_generating() -> None:
    """runner는 아직 running이라고 보고해도, 스트림에 DONE이 이미 있으면 false로 보정한다."""
    runner = MagicMock()
    runner.is_running = MagicMock(return_value=True)
    event_store = MagicMock()
    event_store.get_tail_id = AsyncMock(return_value=(None, True))

    app = _build_app(runner=runner, event_store=event_store)
    session_id = uuid.uuid4()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/chat/{session_id}/status")

    assert response.status_code == 200
    assert response.json() == {"is_generating": False, "cutoff_id": None}
