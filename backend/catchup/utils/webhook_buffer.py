"""
Webhook Event Buffer Service

Redis-based event buffering with 1-hour accumulation window.
Webhook 이벤트를 Redis Set에 버퍼링하여 중복을 자동 제거하고,
스케줄러가 주기적으로 flush하여 incremental sync를 트리거합니다.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from catchup.utils.redis import get_redis_client

logger = logging.getLogger(__name__)

# Redis key prefixes
WEBHOOK_EVENT_PREFIX = "webhook:events"
WEBHOOK_FLUSH_PREFIX = "webhook:flush"

# TTL settings
EVENT_BUFFER_TTL = 3900  # 65 minutes (1 hour + 5 min buffer)
FLUSH_METADATA_TTL = 7200  # 2 hours


class WebhookEventBuffer:
    """
    Webhook 이벤트 버퍼 관리

    Redis Set을 사용하여 이벤트를 버퍼링합니다.
    Set의 특성상 동일한 이벤트가 여러 번 들어와도 자동으로 중복 제거됩니다.
    """

    def __init__(self):
        self.redis: Redis | None = None

    async def _get_redis(self) -> Redis:
        """Redis 클라이언트 lazy initialization"""
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis

    # ============================================================
    # GitHub Events
    # ============================================================

    async def buffer_github_event(
        self,
        installation_id: int,
        repo_id: int,
        entity_type: str,  # "issue" or "pull_request"
        entity_id: int,    # issue number or PR number
        action: str,       # "opened", "edited", "closed", etc.
    ) -> None:
        """
        GitHub Issue/PR 이벤트를 Redis에 버퍼링

        Args:
            installation_id: GitHub App Installation ID
            repo_id: Repository ID
            entity_type: "issue" 또는 "pull_request"
            entity_id: Issue number 또는 PR number
            action: 이벤트 액션 (opened, edited, closed 등)
        """
        redis = await self._get_redis()

        # Redis key: webhook:events:github:{installation_id}:{repo_id}:{entity_type}
        key = f"{WEBHOOK_EVENT_PREFIX}:github:{installation_id}:{repo_id}:{entity_type}"

        # Event data (JSON string stored in Set)
        event_data = json.dumps({
            "id": entity_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).timestamp()
        })

        # Add to Redis Set (자동 중복 제거)
        await redis.sadd(key, event_data)

        # Set TTL (65분)
        await redis.expire(key, EVENT_BUFFER_TTL)

        logger.info(
            f"Buffered GitHub {entity_type} event: "
            f"installation={installation_id}, repo={repo_id}, id={entity_id}, action={action}"
        )

    async def get_github_buffered_repos(
        self, installation_id: int
    ) -> list[tuple[int, str]]:
        """
        버퍼링된 이벤트가 있는 Repository 목록 조회

        Args:
            installation_id: GitHub App Installation ID

        Returns:
            [(repo_id, entity_type), ...] 형태의 리스트
            예: [(456, "issue"), (456, "pull_request"), (789, "issue")]
        """
        redis = await self._get_redis()
        pattern = f"{WEBHOOK_EVENT_PREFIX}:github:{installation_id}:*"

        repos_with_events = []

        # Scan all keys matching pattern
        async for key in redis.scan_iter(match=pattern):
            key_str = key.decode() if isinstance(key, bytes) else key
            # Parse: webhook:events:github:{inst_id}:{repo_id}:{type}
            parts = key_str.split(":")
            if len(parts) == 6:
                repo_id = int(parts[4])
                entity_type = parts[5]
                repos_with_events.append((repo_id, entity_type))

        return repos_with_events

    async def clear_github_buffer(
        self, installation_id: int, repo_id: int, entity_type: str
    ) -> int:
        """
        버퍼링된 이벤트 삭제 및 카운트 반환

        Args:
            installation_id: GitHub App Installation ID
            repo_id: Repository ID
            entity_type: "issue" 또는 "pull_request"

        Returns:
            삭제된 이벤트 개수
        """
        redis = await self._get_redis()
        key = f"{WEBHOOK_EVENT_PREFIX}:github:{installation_id}:{repo_id}:{entity_type}"

        # Get count before deletion
        count = await redis.scard(key)

        # Delete the key
        await redis.delete(key)

        # Record flush timestamp (모니터링용)
        flush_key = f"{WEBHOOK_FLUSH_PREFIX}:github:{installation_id}:{repo_id}"
        await redis.set(flush_key, datetime.now(timezone.utc).isoformat(), ex=FLUSH_METADATA_TTL)

        return count

    # ============================================================
    # Slack Events
    # ============================================================

    async def buffer_slack_event(
        self,
        team_id: str,
        channel_id: str,
        message_ts: str,
        event_type: str = "message",
    ) -> None:
        """
        Slack message 이벤트를 Redis에 버퍼링

        Args:
            team_id: Slack Team/Workspace ID
            channel_id: Channel ID
            message_ts: Message timestamp (Slack의 고유 메시지 ID)
            event_type: 이벤트 타입 (기본값: "message")
        """
        redis = await self._get_redis()

        key = f"{WEBHOOK_EVENT_PREFIX}:slack:{team_id}:{channel_id}:message"
        event_data = json.dumps({
            "ts": message_ts,
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).timestamp()
        })

        await redis.sadd(key, event_data)
        await redis.expire(key, EVENT_BUFFER_TTL)

        logger.info(
            f"Buffered Slack message event: team={team_id}, channel={channel_id}, ts={message_ts}"
        )

    async def get_slack_buffered_channels(
        self, team_id: str
    ) -> list[str]:
        """
        버퍼링된 이벤트가 있는 Channel 목록 조회

        Args:
            team_id: Slack Team/Workspace ID

        Returns:
            Channel ID 리스트
        """
        redis = await self._get_redis()
        pattern = f"{WEBHOOK_EVENT_PREFIX}:slack:{team_id}:*"

        channels = []
        async for key in redis.scan_iter(match=pattern):
            key_str = key.decode() if isinstance(key, bytes) else key
            # Parse: webhook:events:slack:{team_id}:{channel_id}:message
            parts = key_str.split(":")
            if len(parts) == 6:
                channel_id = parts[4]
                channels.append(channel_id)

        return list(set(channels))  # 중복 제거

    async def clear_slack_buffer(
        self, team_id: str, channel_id: str
    ) -> int:
        """
        버퍼링된 이벤트 삭제 및 카운트 반환

        Args:
            team_id: Slack Team/Workspace ID
            channel_id: Channel ID

        Returns:
            삭제된 이벤트 개수
        """
        redis = await self._get_redis()
        key = f"{WEBHOOK_EVENT_PREFIX}:slack:{team_id}:{channel_id}:message"

        count = await redis.scard(key)
        await redis.delete(key)

        # Record flush timestamp
        flush_key = f"{WEBHOOK_FLUSH_PREFIX}:slack:{team_id}"
        await redis.set(flush_key, datetime.now(timezone.utc).isoformat(), ex=FLUSH_METADATA_TTL)

        return count

    # ============================================================
    # Jira Events
    # ============================================================

    async def buffer_jira_event(
        self,
        cloud_id: str,
        project_key: str,
        issue_key: str,
        event_type: str,  # "issue_created", "issue_updated", etc.
    ) -> None:
        """
        Jira issue 이벤트를 Redis에 버퍼링

        Args:
            cloud_id: Jira Cloud ID
            project_key: Project Key (예: "CAT")
            issue_key: Issue Key (예: "CAT-123")
            event_type: Jira 이벤트 타입 (jira:issue_created 등)
        """
        redis = await self._get_redis()

        key = f"{WEBHOOK_EVENT_PREFIX}:jira:{cloud_id}:{project_key}:issue"
        event_data = json.dumps({
            "key": issue_key,
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).timestamp()
        })

        await redis.sadd(key, event_data)
        await redis.expire(key, EVENT_BUFFER_TTL)

        logger.info(
            f"Buffered Jira issue event: cloud={cloud_id}, project={project_key}, issue={issue_key}"
        )

    async def get_jira_buffered_projects(
        self, cloud_id: str
    ) -> list[str]:
        """
        버퍼링된 이벤트가 있는 Project 목록 조회

        Args:
            cloud_id: Jira Cloud ID

        Returns:
            Project Key 리스트
        """
        redis = await self._get_redis()
        pattern = f"{WEBHOOK_EVENT_PREFIX}:jira:{cloud_id}:*"

        projects = []
        async for key in redis.scan_iter(match=pattern):
            key_str = key.decode() if isinstance(key, bytes) else key
            # Parse: webhook:events:jira:{cloud_id}:{project_key}:issue
            parts = key_str.split(":")
            if len(parts) == 6:
                project_key = parts[4]
                projects.append(project_key)

        return list(set(projects))  # 중복 제거

    async def clear_jira_buffer(
        self, cloud_id: str, project_key: str
    ) -> int:
        """
        버퍼링된 이벤트 삭제 및 카운트 반환

        Args:
            cloud_id: Jira Cloud ID
            project_key: Project Key

        Returns:
            삭제된 이벤트 개수
        """
        redis = await self._get_redis()
        key = f"{WEBHOOK_EVENT_PREFIX}:jira:{cloud_id}:{project_key}:issue"

        count = await redis.scard(key)
        await redis.delete(key)

        # Record flush timestamp
        flush_key = f"{WEBHOOK_FLUSH_PREFIX}:jira:{cloud_id}"
        await redis.set(flush_key, datetime.now(timezone.utc).isoformat(), ex=FLUSH_METADATA_TTL)

        return count


# ============================================================
# Singleton Instance
# ============================================================

_buffer_instance: WebhookEventBuffer | None = None


def get_webhook_buffer() -> WebhookEventBuffer:
    """
    Singleton pattern으로 WebhookEventBuffer 인스턴스 반환

    Returns:
        WebhookEventBuffer 인스턴스
    """
    global _buffer_instance
    if _buffer_instance is None:
        _buffer_instance = WebhookEventBuffer()
    return _buffer_instance
