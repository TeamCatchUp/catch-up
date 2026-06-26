from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
from catchup.automations.config import InquiryAutomationConfig
from catchup.automations.schemas import InquiryAutomationItem
from catchup.automations.schemas import InquiryAutomationPatch
from catchup.automations.schemas import InquiryAutomationPublishResult
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.db.agent_triggers import AgentTriggerDefinition
from catchup.db.agent_triggers import AgentTriggerDefinitionError
from catchup.db.agent_triggers import create_or_update_agent_trigger_from_definition
from catchup.db.automations import get_inquiry_agent_spec_for_update
from catchup.db.automations import get_inquiry_agent_spec_with_user
from catchup.db.automations import list_inquiry_agent_specs
from catchup.db.automations import upsert_inquiry_agent_spec
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus
from catchup.db.models import SlackChannel
from catchup.db.slack.domain_repository import get_channels_by_team
from catchup.db.slack.oauth_repository import get_all_slack_tokens
from catchup.db.slack.oauth_repository import get_slack_token_by_id

_AGENT_ID_NAMESPACE = uuid.UUID("8d94ed94-b9c1-47b6-8716-e7a69e778a95")


class AutomationNotFoundError(ValueError):
    """요청한 Automation이 존재하지 않는다."""


class AutomationForbiddenError(ValueError):
    """수정 권한이 없는 사용자가 변경을 시도한다."""


class AutomationPublishError(ValueError):
    """publish 유효성 검증 실패."""

    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status



def build_agent_id(
    *,
    workspace_id: int,
    preset_key: str,
    channel_talk_channel_id: str,
    slack_channel_id: str,
) -> uuid.UUID:
    """agent_id를 결정론적으로 생성한다. 동일 파라미터라면 항상 같은 UUID를 반환한다."""
    return uuid.uuid5(
        _AGENT_ID_NAMESPACE,
        ":".join(
            [
                str(workspace_id),
                preset_key,
                channel_talk_channel_id,
                slack_channel_id,
            ]
        ),
    )


def build_channel_talk_debounce_condition(
    *,
    channel_id: str,
    quiet_period_seconds: int,
) -> dict[str, Any]:
    """ChannelTalk debounce trigger 조건을 생성한다."""
    channel_boundary = {
        "path": "$.payload.entity.channelId",
        "op": "eq",
        "value": channel_id,
    }
    return {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": quiet_period_seconds,
        "run_context": "latest_event",
        "where": {"all": [channel_boundary]},
        "reset_where": {
            "all": [
                channel_boundary,
                {
                    "path": "$.payload.entity.personType",
                    "op": "eq",
                    "value": "user",
                },
            ]
        },
    }


def validate_slack_channel_access(
    *,
    bot_access_token: str,
    team_id: str,
    channel_id: str,
) -> None:
    """Bot이 채널 history를 읽을 수 있는지 검증한다. 실패 시 AutomationPublishError를 발생시킨다."""

    async def _probe() -> None:
        client = SlackApiClientWrapper(bot_access_token, team_id)
        await client.get_conversation_history(channel=channel_id, limit=1)

    try:
        asyncio.run(_probe())
    except SlackConnectorApiError as exc:
        error_code = exc.metadata.get("error") if exc.metadata else None
        raise AutomationPublishError(
            "Bot does not have access to the requested Slack Channel."
            + (f": {error_code}" if error_code else "")
        ) from exc


class InquiryAutomationService:

    def get_automation(
        self,
        db: Session,
        *,
        agent_spec_id: int,
        workspace_id: int,
        current_user_id: int,
    ) -> InquiryAutomationItem:
        """단일 문의 자동화를 조회한다. 존재하지 않으면 AutomationNotFoundError를 발생시킨다."""
        row = get_inquiry_agent_spec_with_user(db, agent_spec_id, workspace_id)
        if row is None:
            raise AutomationNotFoundError("Automation not found")
        spec_row, author = row
        try:
            config = InquiryAutomationConfig.model_validate(spec_row.spec)
        except Exception as exc:
            raise AutomationNotFoundError("Automation spec is invalid") from exc
        trigger = spec_row.triggers[0] if spec_row.triggers else None
        quiet_period_seconds = (
            trigger.condition.get("quiet_period_seconds")
            if trigger is not None
            else None
        )
        title = spec_row.spec.get("title") or spec_row.spec.get("name")
        if not isinstance(title, str) or not title.strip():
            title = "채널톡 문의 자동화"
        return InquiryAutomationItem(
            agent_spec_id=spec_row.id,
            status=spec_row.status,
            channel_talk_credential_id=config.channel_talk_credential_id,
            slack_channel_id=config.slack_channel_id,
            slack_credential_id=config.slack_credential_id,
            guide_instruction=config.guide_instruction,
            quiet_period_seconds=quiet_period_seconds,
            trigger_id=trigger.id if trigger is not None else None,
            title=title.strip(),
            author_name=author.name,
            updated_at=spec_row.updated_at.isoformat(),
            author_profile_image_url=author.picture,
            is_editable=spec_row.user_id == current_user_id,
        )

    def list_automations(
        self,
        db: Session,
        workspace_id: int,
        current_user_id: int,
    ) -> list[InquiryAutomationItem]:
        """워크스페이스에 등록된 문의 자동화 목록을 반환한다."""
        rows = list_inquiry_agent_specs(db, workspace_id)
        items: list[InquiryAutomationItem] = []
        for row, author in rows:
            try:
                config = InquiryAutomationConfig.model_validate(row.spec)
            except Exception:
                continue
            trigger = row.triggers[0] if row.triggers else None
            quiet_period_seconds = (
                trigger.condition.get("quiet_period_seconds")
                if trigger is not None
                else None
            )
            title = row.spec.get("title") or row.spec.get("name")
            if not isinstance(title, str) or not title.strip():
                title = "채널톡 문의 자동화"
            items.append(
                InquiryAutomationItem(
                    agent_spec_id=row.id,
                    status=row.status,
                    channel_talk_credential_id=config.channel_talk_credential_id,
                    slack_channel_id=config.slack_channel_id,
                    slack_credential_id=config.slack_credential_id,
                    guide_instruction=config.guide_instruction,
                    quiet_period_seconds=quiet_period_seconds,
                    trigger_id=trigger.id if trigger is not None else None,
                    title=title.strip(),
                    author_name=author.name,
                    updated_at=row.updated_at.isoformat(),
                    author_profile_image_url=author.picture,
                    is_editable=row.user_id == current_user_id,
                )
            )
        return items

    def update_status(
        self,
        db: Session,
        *,
        agent_spec_id: int,
        workspace_id: int,
        requesting_user_id: int,
        new_status: AgentStatus,
    ) -> None:
        """문의 자동화 상태를 변경한다. 존재하지 않으면 AutomationNotFoundError를 발생시킨다."""
        agent_spec = get_inquiry_agent_spec_for_update(db, agent_spec_id, workspace_id)
        if agent_spec is None:
            raise AutomationNotFoundError("Automation not found")
        if agent_spec.user_id != requesting_user_id:
            raise AutomationForbiddenError("Only the author can modify this automation")
        agent_spec.status = new_status
        db.commit()

    def patch_settings(
        self,
        db: Session,
        *,
        agent_spec_id: int,
        workspace_id: int,
        user_id: int,
        patch: InquiryAutomationPatch,
    ) -> None:
        """문의 자동화 설정을 부분 수정한다. 제공된 필드만 반영하며 status는 변경하지 않는다."""
        agent_spec = get_inquiry_agent_spec_for_update(db, agent_spec_id, workspace_id)
        if agent_spec is None:
            raise AutomationNotFoundError("Automation not found")
        if agent_spec.user_id != user_id:
            raise AutomationForbiddenError("Only the author can modify this automation")

        config = InquiryAutomationConfig.model_validate(agent_spec.spec)
        trigger = agent_spec.triggers[0] if agent_spec.triggers else None

        new_ct_credential_id = (
            patch.channel_talk_credential_id or config.channel_talk_credential_id
        )
        new_slack_credential_id = config.slack_credential_id
        new_slack_channel_id = config.slack_channel_id
        if patch.slack_channel is not None:
            new_slack_credential_id = patch.slack_channel.credential_id
            new_slack_channel_id = patch.slack_channel.channel_id

        if patch.quiet_period_seconds is not None:
            new_quiet_period_seconds = patch.quiet_period_seconds
        elif trigger is not None and trigger.condition.get("quiet_period_seconds") is not None:
            new_quiet_period_seconds = int(trigger.condition["quiet_period_seconds"])
        else:
            new_quiet_period_seconds = 60

        new_guide_instruction = (
            patch.guide_instruction
            if "guide_instruction" in patch.model_fields_set
            else config.guide_instruction
        )

        ct_credential = ChannelTalkCredentialsRepository(db).get_connection_by_id(
            new_ct_credential_id
        )
        if ct_credential is None:
            raise AutomationPublishError(
                "Channel Talk credentials not found", http_status=404
            )
        if not ct_credential.webhook_token_configured:
            raise AutomationPublishError(
                "Channel Talk webhook token is not configured"
            )

        slack_changed = (
            new_slack_channel_id != config.slack_channel_id
            or new_slack_credential_id != config.slack_credential_id
        )
        if slack_changed:
            self._resolve_slack_channel(
                db,
                slack_credential_id=new_slack_credential_id,
                slack_channel_id=new_slack_channel_id,
            )

        new_agent_id = build_agent_id(
            workspace_id=workspace_id,
            preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
            channel_talk_channel_id=ct_credential.channel_id,
            slack_channel_id=new_slack_channel_id,
        )
        if new_agent_id != agent_spec.agent_id:
            conflict = db.scalar(
                select(AgentSpec).where(AgentSpec.agent_id == new_agent_id)
            )
            if conflict is not None:
                raise AutomationPublishError(
                    "An automation for this channel combination already exists"
                )
            agent_spec.agent_id = new_agent_id

        agent_spec.spec = InquiryAutomationConfig(
            preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
            channel_talk_credential_id=new_ct_credential_id,
            slack_channel_id=new_slack_channel_id,
            slack_credential_id=new_slack_credential_id,
            guide_instruction=new_guide_instruction,
            quiet_period_seconds=new_quiet_period_seconds,
        ).model_dump(mode="json")
        agent_spec.user_id = user_id

        condition = build_channel_talk_debounce_condition(
            channel_id=ct_credential.channel_id,
            quiet_period_seconds=new_quiet_period_seconds,
        )
        try:
            create_or_update_agent_trigger_from_definition(
                db,
                AgentTriggerDefinition(
                    agent_spec_id=agent_spec.id,
                    workspace_id=agent_spec.workspace_id,
                    name=(
                        f"Channel Talk debounce - {ct_credential.channel_name}"
                    ),
                    source="channel_talk",
                    event_type="user_chat.created",
                    condition=condition,
                    concurrency_key=(
                        f"channel_talk:{ct_credential.channel_id}:user_chat"
                    ),
                ),
            )
            db.commit()
        except AgentTriggerDefinitionError as exc:
            db.rollback()
            raise AutomationPublishError(str(exc)) from exc
        except Exception:
            db.rollback()
            raise

    def publish(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        channel_talk_credential_id: int,
        quiet_period_seconds: int,
        slack_credential_id: int,
        slack_channel_id: str,
        guide_instruction: str | None,
    ) -> InquiryAutomationPublishResult:
        """채널톡-슬랙 문의 자동화를 생성 또는 재활성화한다."""
        channel_talk_credential = ChannelTalkCredentialsRepository(
            db
        ).get_connection_by_id(channel_talk_credential_id)
        if channel_talk_credential is None:
            raise AutomationPublishError(
                "Channel Talk credentials not found", http_status=404
            )
        if not channel_talk_credential.webhook_token_configured:
            raise AutomationPublishError(
                "Channel Talk webhook token is not configured"
            )

        self._resolve_slack_channel(
            db,
            slack_credential_id=slack_credential_id,
            slack_channel_id=slack_channel_id,
        )

        agent_id = build_agent_id(
            workspace_id=workspace_id,
            preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
            channel_talk_channel_id=channel_talk_credential.channel_id,
            slack_channel_id=slack_channel_id,
        )
        config = InquiryAutomationConfig(
            preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
            channel_talk_credential_id=channel_talk_credential_id,
            slack_channel_id=slack_channel_id,
            slack_credential_id=slack_credential_id,
            guide_instruction=guide_instruction,
            quiet_period_seconds=quiet_period_seconds,
        )
        agent_spec = upsert_inquiry_agent_spec(
            db,
            agent_id=agent_id,
            workspace_id=workspace_id,
            user_id=user_id,
            spec=config.model_dump(mode="json"),
        )

        condition = build_channel_talk_debounce_condition(
            channel_id=channel_talk_credential.channel_id,
            quiet_period_seconds=quiet_period_seconds,
        )
        try:
            trigger = create_or_update_agent_trigger_from_definition(
                db,
                AgentTriggerDefinition(
                    agent_spec_id=agent_spec.id,
                    workspace_id=agent_spec.workspace_id,
                    name=(
                        f"Channel Talk debounce"
                        f" - {channel_talk_credential.channel_name}"
                    ),
                    source="channel_talk",
                    event_type="user_chat.created",
                    condition=condition,
                    concurrency_key=(
                        f"channel_talk:{channel_talk_credential.channel_id}:user_chat"
                    ),
                ),
            )
            db.commit()
        except AgentTriggerDefinitionError as exc:
            db.rollback()
            raise AutomationPublishError(str(exc)) from exc
        except Exception:
            db.rollback()
            raise

        return InquiryAutomationPublishResult(
            agent_spec_id=agent_spec.id,
            trigger_id=trigger.id,
            status=agent_spec.status,
            channel_talk_channel_id=channel_talk_credential.channel_id,
            channel_talk_channel_name=channel_talk_credential.channel_name,
            quiet_period_seconds=quiet_period_seconds,
            slack_channel_id=slack_channel_id,
        )

    def list_slack_targets(
        self,
        db: Session,
        *,
        credential_id: int | None,
    ) -> list[dict[str, Any]]:
        """Slack 채널 target 목록을 반환한다."""
        if credential_id is None:
            tokens = get_all_slack_tokens(db)
        else:
            token = get_slack_token_by_id(db, credential_id)
            if token is None:
                raise AutomationPublishError(
                    "Slack credentials not found", http_status=404
                )
            tokens = [token]

        targets: list[dict[str, Any]] = []
        for token in tokens:
            for channel in get_channels_by_team(db, str(token.team_id)):
                channel_name = _text(channel.name) or str(channel.id)
                targets.append(
                    {
                        "connector": "slack",
                        "credential_id": int(token.id),
                        "target_id": str(channel.id),
                        "display_name": channel_name,
                        "target_type": "channel",
                        "is_accessible": not bool(channel.is_archived),
                        "metadata": {
                            "team_id": str(channel.team_id),
                            "team_name": _text(token.team_name),
                            "channel_name": channel_name,
                            "channel_kind": str(channel.channel_type),
                            "is_private": bool(channel.is_private),
                            "is_archived": bool(channel.is_archived),
                            "member_count": int(channel.member_count or 0),
                        },
                    }
                )
        targets.sort(
            key=lambda t: (t["display_name"].casefold(), t["target_id"])
        )
        return targets

    def list_channel_talk_targets(
        self,
        db: Session,
        *,
        credential_id: int | None,
    ) -> list[dict[str, Any]]:
        """ChannelTalk target 목록을 반환한다."""
        repository = ChannelTalkCredentialsRepository(db)
        if credential_id is None:
            records = repository.list_connections()
        else:
            record = repository.get_connection_by_id(credential_id)
            if record is None:
                raise AutomationPublishError(
                    "Channel Talk credentials not found", http_status=404
                )
            records = [record]

        return [
            {
                "connector": "channel_talk",
                "credential_id": int(record.id),
                "target_id": str(record.channel_id),
                "display_name": str(record.channel_name),
                "target_type": "channel",
                "is_accessible": bool(record.webhook_token_configured),
                "metadata": {
                    "channel_id": str(record.channel_id),
                    "channel_name": str(record.channel_name),
                    "webhook_token_configured": bool(record.webhook_token_configured),
                },
            }
            for record in records
            if record.id is not None
        ]

    def _resolve_slack_channel(
        self,
        db: Session,
        *,
        slack_credential_id: int,
        slack_channel_id: str,
    ) -> None:
        """Slack 채널 존재 여부, 팀 귀속, 아카이브 여부, Bot 접근 권한을 검증한다."""
        slack_token = get_slack_token_by_id(db, slack_credential_id)
        if slack_token is None:
            raise AutomationPublishError(
                "Slack credentials not found", http_status=404
            )
        if not slack_token.bot_access_token or not slack_token.team_id:
            raise AutomationPublishError("Slack credentials are incomplete")

        channel = db.get(SlackChannel, slack_channel_id)
        if channel is not None:
            if channel.team_id != slack_token.team_id:
                raise AutomationPublishError(
                    "Slack channel does not belong to the selected credentials"
                )
            if channel.is_archived:
                raise AutomationPublishError("Slack channel is archived")

        validate_slack_channel_access(
            bot_access_token=slack_token.bot_access_token,
            team_id=slack_token.team_id,
            channel_id=slack_channel_id,
        )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
