from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from catchup.auth.dependencies import get_current_user
from catchup.automations import service as automations_service
from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
from catchup.automations.schemas import InquiryAutomationPatch
from catchup.automations.schemas import SlackChannelSelection
from catchup.automations.service import AutomationNotFoundError
from catchup.automations.service import AutomationPublishError
from catchup.automations.service import InquiryAutomationService
from catchup.automations.service import build_agent_id
from catchup.automations.service import build_channel_talk_debounce_condition
from catchup.automations.service import validate_slack_channel_access
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.db.dependencies import get_db
from catchup.db.models import AgentStatus
from catchup.server.automations import api
from catchup.server.automations.api import InquiryAutomationPublishRequest
from catchup.server.automations.api import list_automation_credentials
from catchup.server.automations.api import list_automation_targets
from catchup.server.automations.api import list_inquiry_automations
from catchup.server.automations.api import patch_inquiry_automation_settings
from catchup.server.automations.api import router
from catchup.server.automations.api import update_inquiry_automation


def test_publish_request_requires_slack_channel() -> None:
    with pytest.raises(ValidationError):
        InquiryAutomationPublishRequest.model_validate(
            {
                "channel_talk_credential_id": 7,
                "quiet_period_seconds": 60,
            }
        )


def test_publish_request_guide_instruction_is_optional() -> None:
    req = InquiryAutomationPublishRequest.model_validate(
        {
            "channel_talk_credential_id": 7,
            "quiet_period_seconds": 60,
            "slack_channel": {
                "credential_id": 1,
                "channel_id": "C123",
            },
        }
    )
    assert req.guide_instruction is None


def test_publish_request_accepts_guide_instruction() -> None:
    req = InquiryAutomationPublishRequest.model_validate(
        {
            "channel_talk_credential_id": 7,
            "quiet_period_seconds": 60,
            "slack_channel": {
                "credential_id": 1,
                "channel_id": "C123",
            },
            "guide_instruction": "결제 문의는 영수증을 요청하세요.",
        }
    )
    assert req.guide_instruction == "결제 문의는 영수증을 요청하세요."


def test_automation_credentials_endpoint_is_registered(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    monkeypatch.setattr(api, "get_all_slack_tokens", lambda _: [])

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/automations/credentials",
            params={"connector": "slack"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "connector": "slack",
        "total_credentials": 0,
        "credentials": [],
    }


def test_list_slack_credentials_returns_selectable_workspaces(monkeypatch) -> None:
    token = SimpleNamespace(
        id=42,
        team_id="T123",
        team_name="CatchUp",
        bot_user_id="U999",
        bot_access_token="xoxb-secret",
        bot_scopes="channels:history,chat:write",
    )
    monkeypatch.setattr(api, "get_all_slack_tokens", lambda _: [token])

    response = list_automation_credentials(
        connector="slack",
        db=MagicMock(),
        current_user=SimpleNamespace(id=1),
    )

    assert response.model_dump(mode="json") == {
        "connector": "slack",
        "total_credentials": 1,
        "credentials": [
            {
                "connector": "slack",
                "credential_id": 42,
                "display_name": "CatchUp",
                "external_id": "T123",
                "external_name": "CatchUp",
                "is_configured": True,
                "metadata": {
                    "team_id": "T123",
                    "team_name": "CatchUp",
                    "bot_user_id": "U999",
                    "bot_scopes": "channels:history,chat:write",
                },
            }
        ],
    }


def test_list_channel_talk_credentials_returns_selectable_channels(monkeypatch) -> None:
    repository = SimpleNamespace(
        list_connections=lambda: [
            SimpleNamespace(
                id=7,
                channel_id="ch-001",
                channel_name="Support",
                credential_last_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                webhook_token_configured=True,
            )
        ]
    )
    monkeypatch.setattr(
        api,
        "ChannelTalkCredentialsRepository",
        lambda _: repository,
    )

    response = list_automation_credentials(
        connector="channel_talk",
        db=MagicMock(),
        current_user=SimpleNamespace(id=1),
    )

    assert response.model_dump(mode="json") == {
        "connector": "channel_talk",
        "total_credentials": 1,
        "credentials": [
            {
                "connector": "channel_talk",
                "credential_id": 7,
                "display_name": "Support",
                "external_id": "ch-001",
                "external_name": "Support",
                "is_configured": True,
                "metadata": {
                    "channel_id": "ch-001",
                    "channel_name": "Support",
                    "credential_last_verified_at": "2026-01-01T00:00:00+00:00",
                    "webhook_token_configured": True,
                },
            }
        ],
    }


def test_list_slack_targets_returns_channels_for_selected_credential(monkeypatch) -> None:
    token = SimpleNamespace(id=42, team_id="T123", team_name="CatchUp")
    channel = SimpleNamespace(
        id="C123",
        team_id="T123",
        name="cs-alerts",
        channel_type="public",
        is_private=False,
        is_archived=False,
        member_count=12,
    )
    monkeypatch.setattr(automations_service, "get_slack_token_by_id", lambda *_: token)
    monkeypatch.setattr(automations_service, "get_channels_by_team", lambda *_: [channel])

    response = list_automation_targets(
        connector="slack",
        db=MagicMock(),
        current_user=SimpleNamespace(id=1),
        credential_id=42,
    )

    assert response.model_dump(mode="json") == {
        "connector": "slack",
        "credential_id": 42,
        "total_targets": 1,
        "targets": [
            {
                "connector": "slack",
                "credential_id": 42,
                "target_id": "C123",
                "display_name": "cs-alerts",
                "target_type": "channel",
                "is_accessible": True,
                "metadata": {
                    "team_id": "T123",
                    "team_name": "CatchUp",
                    "channel_name": "cs-alerts",
                    "channel_kind": "public",
                    "is_private": False,
                    "is_archived": False,
                    "member_count": 12,
                },
            }
        ],
    }


def test_list_channel_talk_targets_returns_selected_channel(monkeypatch) -> None:
    repository = SimpleNamespace(
        get_connection_by_id=lambda credential_id: SimpleNamespace(
            id=credential_id,
            channel_id="ch-001",
            channel_name="Support",
            webhook_token_configured=True,
        )
    )
    monkeypatch.setattr(
        automations_service,
        "ChannelTalkCredentialsRepository",
        lambda _: repository,
    )

    response = list_automation_targets(
        connector="channel_talk",
        db=MagicMock(),
        current_user=SimpleNamespace(id=1),
        credential_id=7,
    )

    assert response.model_dump(mode="json") == {
        "connector": "channel_talk",
        "credential_id": 7,
        "total_targets": 1,
        "targets": [
            {
                "connector": "channel_talk",
                "credential_id": 7,
                "target_id": "ch-001",
                "display_name": "Support",
                "target_type": "channel",
                "is_accessible": True,
                "metadata": {
                    "channel_id": "ch-001",
                    "channel_name": "Support",
                    "webhook_token_configured": True,
                },
            }
        ],
    }


def test_build_agent_id_is_stable_for_idempotency_key() -> None:
    first = build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    second = build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    assert first == second


def test_build_agent_id_differs_for_different_slack_channels() -> None:
    a = build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    b = build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C999",
    )
    assert a != b


def test_build_channel_talk_debounce_condition_resets_only_user_messages() -> None:
    condition = build_channel_talk_debounce_condition(
        channel_id="229395",
        quiet_period_seconds=60,
    )
    assert condition == {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": 60,
        "run_context": "latest_event",
        "where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "229395",
                }
            ]
        },
        "reset_where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "229395",
                },
                {
                    "path": "$.payload.entity.personType",
                    "op": "eq",
                    "value": "user",
                },
            ]
        },
    }


def _make_spec_row(
    *,
    spec_id: int = 1,
    status: AgentStatus = AgentStatus.ACTIVE,
    channel_talk_credential_id: int = 7,
    slack_channel_id: str = "C123",
    slack_credential_id: int = 1,
    guide_instruction: str | None = None,
    quiet_period_seconds: int | None = 60,
    title: str | None = None,
) -> MagicMock:
    trigger = SimpleNamespace(
        id=99,
        condition={"quiet_period_seconds": quiet_period_seconds}
        if quiet_period_seconds is not None
        else {},
    )
    row = MagicMock()
    row.id = spec_id
    row.status = status
    row.spec = {
        "preset_key": INQUIRY_AUTOMATION_PRESET_KEY,
        "channel_talk_credential_id": channel_talk_credential_id,
        "slack_channel_id": slack_channel_id,
        "slack_credential_id": slack_credential_id,
        "guide_instruction": guide_instruction,
    }
    if title is not None:
        row.spec["title"] = title
    row.triggers = [trigger]
    row.updated_at = datetime(2026, 6, 16, 9, 30, tzinfo=timezone.utc)
    return row


def test_list_inquiry_automations_returns_items(monkeypatch) -> None:
    row = _make_spec_row(guide_instruction="환불은 영수증 먼저", title="문의 응대 자동화")
    author = SimpleNamespace(name="팀원A", picture="https://example.com/profile.png")
    db = MagicMock()
    db.execute.return_value.all.return_value = [(row, author)]
    user = SimpleNamespace(id=1)

    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)

    result = list_inquiry_automations(db=db, current_user=user)

    assert len(result) == 1
    assert result[0].agent_spec_id == 1
    assert result[0].status == AgentStatus.ACTIVE
    assert result[0].slack_channel_id == "C123"
    assert result[0].guide_instruction == "환불은 영수증 먼저"
    assert result[0].quiet_period_seconds == 60
    assert result[0].trigger_id == 99
    assert result[0].title == "문의 응대 자동화"
    assert result[0].author_name == "팀원A"
    assert result[0].updated_at == "2026-06-16T09:30:00+00:00"
    assert result[0].author_profile_image_url == "https://example.com/profile.png"


def test_list_inquiry_automations_uses_default_title(monkeypatch) -> None:
    row = _make_spec_row()
    author = SimpleNamespace(name="작성자", picture=None)
    db = MagicMock()
    db.execute.return_value.all.return_value = [(row, author)]
    user = SimpleNamespace(id=1)

    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)

    result = list_inquiry_automations(db=db, current_user=user)

    assert result[0].title == "채널톡 문의 자동화"
    assert result[0].author_name == "작성자"
    assert result[0].author_profile_image_url is None


def test_list_inquiry_automations_skips_invalid_spec(monkeypatch) -> None:
    bad_row = MagicMock()
    bad_row.spec = {"preset_key": INQUIRY_AUTOMATION_PRESET_KEY}
    bad_row.triggers = []
    bad_row.updated_at = datetime(2026, 6, 16, 9, 30, tzinfo=timezone.utc)
    author = SimpleNamespace(name="작성자", picture=None)
    db = MagicMock()
    db.execute.return_value.all.return_value = [(bad_row, author)]
    user = SimpleNamespace(id=1)

    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)

    result = list_inquiry_automations(db=db, current_user=user)

    assert result == []


def test_update_inquiry_automation_sets_inactive(monkeypatch) -> None:
    from catchup.server.automations.api import InquiryAutomationUpdateRequest

    row = _make_spec_row()
    db = MagicMock()
    db.scalar.return_value = row
    user = SimpleNamespace(id=1)

    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)

    update_inquiry_automation(
        agent_spec_id=1,
        body=InquiryAutomationUpdateRequest(status=AgentStatus.INACTIVE),
        db=db,
        current_user=user,
    )

    assert row.status == AgentStatus.INACTIVE
    db.commit.assert_called_once()


def test_update_inquiry_automation_raises_404_when_not_found(monkeypatch) -> None:
    from catchup.server.automations.api import InquiryAutomationUpdateRequest

    db = MagicMock()
    db.scalar.return_value = None
    user = SimpleNamespace(id=1)

    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)

    with pytest.raises(HTTPException) as exc_info:
        update_inquiry_automation(
            agent_spec_id=999,
            body=InquiryAutomationUpdateRequest(status=AgentStatus.INACTIVE),
            db=db,
            current_user=user,
        )

    assert exc_info.value.status_code == 404


def test_validate_slack_channel_history_access_probes_latest_message(
    monkeypatch,
) -> None:
    calls = []

    class FakeSlackClient:
        def __init__(self, access_token: str, team_id: str):
            calls.append(("init", access_token, team_id))

        async def get_conversation_history(self, *, channel: str, limit: int):
            calls.append(("history", channel, limit))
            return {"messages": []}

    monkeypatch.setattr(automations_service, "SlackApiClientWrapper", FakeSlackClient)

    validate_slack_channel_access(
        bot_access_token="xoxb-token",
        team_id="T123",
        channel_id="C123",
    )

    assert calls == [
        ("init", "xoxb-token", "T123"),
        ("history", "C123", 1),
    ]


def test_validate_slack_channel_history_access_rejects_slack_api_error(
    monkeypatch,
) -> None:
    class FakeSlackClient:
        def __init__(self, access_token: str, team_id: str):
            _ = access_token
            _ = team_id

        async def get_conversation_history(self, *, channel: str, limit: int):
            _ = channel
            _ = limit
            raise SlackConnectorApiError(
                "not in channel",
                metadata={"error": "not_in_channel"},
            )

    monkeypatch.setattr(automations_service, "SlackApiClientWrapper", FakeSlackClient)

    with pytest.raises(AutomationPublishError) as exc_info:
        validate_slack_channel_access(
            bot_access_token="xoxb-token",
            team_id="T123",
            channel_id="C123",
        )

    assert "not_in_channel" in str(exc_info.value)


# ---------------------------------------------------------------------------
# InquiryAutomationPatch schema
# ---------------------------------------------------------------------------


def test_patch_request_accepts_empty_body() -> None:
    patch = InquiryAutomationPatch.model_validate({})
    assert patch.channel_talk_credential_id is None
    assert patch.quiet_period_seconds is None
    assert patch.slack_channel is None
    assert patch.guide_instruction is None


def test_patch_request_rejects_zero_credential_id() -> None:
    with pytest.raises(ValidationError):
        InquiryAutomationPatch.model_validate({"channel_talk_credential_id": 0})


def test_patch_request_rejects_quiet_period_below_minimum() -> None:
    with pytest.raises(ValidationError):
        InquiryAutomationPatch.model_validate({"quiet_period_seconds": 0})


def test_patch_request_rejects_quiet_period_above_maximum() -> None:
    with pytest.raises(ValidationError):
        InquiryAutomationPatch.model_validate({"quiet_period_seconds": 86_401})


def test_patch_request_guide_instruction_not_in_fields_set_when_omitted() -> None:
    patch = InquiryAutomationPatch.model_validate({})
    assert "guide_instruction" not in patch.model_fields_set


def test_patch_request_guide_instruction_in_fields_set_when_explicitly_null() -> None:
    patch = InquiryAutomationPatch.model_validate({"guide_instruction": None})
    assert "guide_instruction" in patch.model_fields_set


# ---------------------------------------------------------------------------
# patch_inquiry_automation_settings router handler
# ---------------------------------------------------------------------------


def test_patch_settings_returns_204_on_success(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)
    monkeypatch.setattr(InquiryAutomationService, "patch_settings", lambda *_, **__: None)

    patch_inquiry_automation_settings(
        agent_spec_id=1,
        body=InquiryAutomationPatch(),
        db=MagicMock(),
        current_user=SimpleNamespace(id=1),
    )


def test_patch_settings_raises_404_when_not_found(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)
    monkeypatch.setattr(
        InquiryAutomationService,
        "patch_settings",
        lambda *_, **__: (_ for _ in ()).throw(AutomationNotFoundError("not found")),
    )

    with pytest.raises(HTTPException) as exc_info:
        patch_inquiry_automation_settings(
            agent_spec_id=999,
            body=InquiryAutomationPatch(),
            db=MagicMock(),
            current_user=SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 404


def test_patch_settings_raises_400_on_channel_conflict(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_workspace_id_for_user", lambda *_: 1)
    monkeypatch.setattr(
        InquiryAutomationService,
        "patch_settings",
        lambda *_, **__: (_ for _ in ()).throw(
            AutomationPublishError("An automation for this channel combination already exists")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        patch_inquiry_automation_settings(
            agent_spec_id=1,
            body=InquiryAutomationPatch(
                slack_channel=SlackChannelSelection(credential_id=2, channel_id="C999")
            ),
            db=MagicMock(),
            current_user=SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 400
    assert "channel combination" in exc_info.value.detail


# ---------------------------------------------------------------------------
# InquiryAutomationService.patch_settings logic
# ---------------------------------------------------------------------------


def _make_patch_env(
    *,
    guide_instruction: str | None = "기존 가이드",
    quiet_period_seconds: int = 60,
    ct_credential_id: int = 7,
    slack_credential_id: int = 1,
    slack_channel_id: str = "C123",
    ct_channel_id: str = "229395",
    agent_id: object = object(),
):
    """patch_settings 호출에 필요한 mock 환경을 구성한다."""
    spec_row = MagicMock()
    spec_row.id = 1
    spec_row.workspace_id = 10
    spec_row.agent_id = agent_id
    spec_row.user_id = 99
    spec_row.spec = {
        "preset_key": INQUIRY_AUTOMATION_PRESET_KEY,
        "channel_talk_credential_id": ct_credential_id,
        "slack_channel_id": slack_channel_id,
        "slack_credential_id": slack_credential_id,
        "guide_instruction": guide_instruction,
        "quiet_period_seconds": quiet_period_seconds,
    }
    spec_row.triggers = [
        SimpleNamespace(
            id=99,
            condition={"quiet_period_seconds": quiet_period_seconds},
        )
    ]

    ct_credential = SimpleNamespace(
        id=ct_credential_id,
        channel_id=ct_channel_id,
        channel_name="Support",
        webhook_token_configured=True,
    )
    ct_repo = SimpleNamespace(get_connection_by_id=lambda _: ct_credential)

    db = MagicMock()
    db.scalar.return_value = None  # no agent_id conflict

    return spec_row, ct_repo, db


def test_patch_settings_preserves_guide_instruction_when_not_provided(
    monkeypatch,
) -> None:
    spec_row, ct_repo, db = _make_patch_env(guide_instruction="보존되어야 함")
    monkeypatch.setattr(
        automations_service,
        "get_inquiry_agent_spec_for_update",
        lambda *_: spec_row,
    )
    monkeypatch.setattr(
        automations_service,
        "ChannelTalkCredentialsRepository",
        lambda _: ct_repo,
    )
    monkeypatch.setattr(
        automations_service,
        "create_or_update_agent_trigger_from_definition",
        lambda *_: SimpleNamespace(id=99),
    )

    InquiryAutomationService().patch_settings(
        db,
        agent_spec_id=1,
        workspace_id=10,
        user_id=5,
        patch=InquiryAutomationPatch(),
    )

    saved_spec = spec_row.spec
    assert saved_spec["guide_instruction"] == "보존되어야 함"


def test_patch_settings_clears_guide_instruction_when_explicitly_null(
    monkeypatch,
) -> None:
    spec_row, ct_repo, db = _make_patch_env(guide_instruction="삭제되어야 함")
    monkeypatch.setattr(
        automations_service,
        "get_inquiry_agent_spec_for_update",
        lambda *_: spec_row,
    )
    monkeypatch.setattr(
        automations_service,
        "ChannelTalkCredentialsRepository",
        lambda _: ct_repo,
    )
    monkeypatch.setattr(
        automations_service,
        "create_or_update_agent_trigger_from_definition",
        lambda *_: SimpleNamespace(id=99),
    )

    InquiryAutomationService().patch_settings(
        db,
        agent_spec_id=1,
        workspace_id=10,
        user_id=5,
        patch=InquiryAutomationPatch(guide_instruction=None),
    )

    saved_spec = spec_row.spec
    assert saved_spec["guide_instruction"] is None


def test_patch_settings_uses_trigger_quiet_period_as_fallback(monkeypatch) -> None:
    spec_row, ct_repo, db = _make_patch_env(quiet_period_seconds=120)
    captured: list[dict] = []
    monkeypatch.setattr(
        automations_service,
        "get_inquiry_agent_spec_for_update",
        lambda *_: spec_row,
    )
    monkeypatch.setattr(
        automations_service,
        "ChannelTalkCredentialsRepository",
        lambda _: ct_repo,
    )

    def _capture_trigger(db, definition):
        captured.append(definition.condition)
        return SimpleNamespace(id=99)

    monkeypatch.setattr(
        automations_service,
        "create_or_update_agent_trigger_from_definition",
        _capture_trigger,
    )

    InquiryAutomationService().patch_settings(
        db,
        agent_spec_id=1,
        workspace_id=10,
        user_id=5,
        patch=InquiryAutomationPatch(),
    )

    assert captured[0]["quiet_period_seconds"] == 120


def test_patch_settings_raises_not_found_when_spec_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        automations_service,
        "get_inquiry_agent_spec_for_update",
        lambda *_: None,
    )

    with pytest.raises(AutomationNotFoundError):
        InquiryAutomationService().patch_settings(
            MagicMock(),
            agent_spec_id=999,
            workspace_id=10,
            user_id=5,
            patch=InquiryAutomationPatch(),
        )
