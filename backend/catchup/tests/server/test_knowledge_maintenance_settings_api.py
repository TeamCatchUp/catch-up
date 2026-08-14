from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from catchup.server.wiki import api
from catchup.server.wiki.dependencies import MemberContext
from catchup.server.wiki.schemas import (
    TestKnowledgeMaintenanceSettingRequest as SettingRequest,
)


class _FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = None

    def get(self, _model, _identity):
        return object()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def refresh(self, value) -> None:
        self.refreshed = value


def _setting(**overrides):
    values = {
        "id": 3,
        "workspace_id": 11,
        "channel_talk_credential_id": 5,
        "enabled": True,
        "execution_anchor_at": datetime(2026, 8, 15, tzinfo=timezone.utc),
        "interval_minutes": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_update_setting_commits_then_applies_runtime_schedule(monkeypatch) -> None:
    db = _FakeDb()
    setting = _setting()
    applied = []
    monkeypatch.setattr(
        api,
        "upsert_test_knowledge_maintenance_setting",
        lambda *_args, **_kwargs: setting,
    )
    monkeypatch.setattr(
        api,
        "apply_test_knowledge_maintenance_schedule",
        applied.append,
    )
    user = SimpleNamespace(id=1)

    response = api.update_knowledge_maintenance_setting(
        channel_talk_credential_id=5,
        payload=SettingRequest(
            enabled=True,
            execution_anchor_at=setting.execution_anchor_at,
            interval_minutes=30,
        ),
        context=MemberContext(user=user, workspace_id=11),
        db=db,
    )

    assert db.committed is True
    assert db.refreshed is setting
    assert applied == [setting]
    assert response.id == setting.id


def test_update_setting_reports_saved_but_not_applied(monkeypatch) -> None:
    db = _FakeDb()
    setting = _setting()
    monkeypatch.setattr(
        api,
        "upsert_test_knowledge_maintenance_setting",
        lambda *_args, **_kwargs: setting,
    )
    monkeypatch.setattr(
        api,
        "apply_test_knowledge_maintenance_schedule",
        lambda _setting: (_ for _ in ()).throw(RuntimeError("scheduler down")),
    )
    user = SimpleNamespace(id=1)

    with pytest.raises(HTTPException) as caught:
        api.update_knowledge_maintenance_setting(
            channel_talk_credential_id=5,
            payload=SettingRequest(
                enabled=True,
                execution_anchor_at=setting.execution_anchor_at,
                interval_minutes=30,
            ),
            context=MemberContext(user=user, workspace_id=11),
            db=db,
        )

    assert db.committed is True
    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == (
        "KNOWLEDGE_MAINTENANCE_SCHEDULE_NOT_APPLIED"
    )
    assert "저장" in caught.value.detail["message"]


def test_settings_router_exposes_get_and_put_endpoints() -> None:
    assert api.router.tags == ["Wiki Channels"]
    paths = {
        (route.path, method)
        for route in api.router.routes
        for method in route.methods
    }
    assert ("/api/v1/wiki/knowledge-maintenance-settings", "GET") in paths
    assert (
        "/api/v1/wiki/knowledge-maintenance-settings/"
        "{channel_talk_credential_id}",
        "PUT",
    ) in paths


def test_setting_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SettingRequest.model_validate(
            {
                "enabled": True,
                "execution_anchor_at": "2026-08-15T00:00:00Z",
                "interval_minutes": 30,
                "unexpected": True,
            }
        )
