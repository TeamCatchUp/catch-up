from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection_by_id,
)
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.db.test_knowledge_maintenance_settings import (
    get_test_knowledge_maintenance_setting,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.user_chat_poller import (
    ChannelTalkUserChatPoller,
)
from catchup.knowledge_maintenance.adapters.llm.block_narrator import LlmBlockNarrator
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.adapters.llm.name_embedder import (
    EmbeddingServiceNameEmbedder,
)
from catchup.knowledge_maintenance.adapters.llm.name_embedder import (
    cached_name_embedder,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    PROMPT_VERSION,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    StructuredKnowledgeExtractor,
)
from catchup.knowledge_maintenance.adapters.postgres.name_embedding_cache import (
    SqlAlchemyNameEmbeddingCache,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbedder
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)
from catchup.knowledge_maintenance.services.run_pre_review_pipeline import (
    PreReviewPipelineResult,
)
from catchup.knowledge_maintenance.services.run_pre_review_pipeline import (
    PreReviewPipelineStatus,
)
from catchup.knowledge_maintenance.services.run_pre_review_pipeline import (
    run_pre_review_pipeline,
)
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

_BACKFILL_DAYS = 30
_LOOKBACK_OVERLAP_MINUTES = 5
_POLL_LIMIT = 50
_MAX_PAGES = 20
_EXTRACTION_CONTRACT_VERSION = "1"
_NARRATION_READ_TIMEOUT_SECONDS = 120


async def run_channel_talk_pre_review_job(
    setting_id: int,
) -> PreReviewPipelineResult | None:
    with SessionLocal() as db:
        setting = get_test_knowledge_maintenance_setting(
            db,
            setting_id=setting_id,
        )
        if setting is None or not setting.enabled:
            return None
        workspace_id = setting.workspace_id
        credential_id = setting.channel_talk_credential_id

    credential = load_channel_talk_connection_by_id(credential_id)
    if credential is None:
        raise RuntimeError(f"ChannelTalk credential not found: {credential_id}")
    if not credential.access_key or not credential.access_secret:
        raise RuntimeError(f"ChannelTalk credential is incomplete: {credential_id}")

    lookback_start = _derive_lookback_start(
        SessionLocal,
        workspace_id=workspace_id,
        channel_id=credential.channel_id,
    )
    poller = ChannelTalkUserChatPoller(
        client=ChannelTalkCoreApiClient(),
        access_key=credential.access_key,
        access_secret=credential.access_secret,
        channel_id=credential.channel_id,
    )
    poll_result = await poller.poll(
        workspace_id=workspace_id,
        lookback_start=lookback_start,
        limit=_POLL_LIMIT,
        max_pages=_MAX_PAGES,
    )
    if poll_result.list_truncated or poll_result.skipped:
        raise RuntimeError(
            "ChannelTalk poll was incomplete: "
            f"list_truncated={poll_result.list_truncated}, "
            f"skipped={len(poll_result.skipped)}"
        )

    uow_factory = _uow_factory(workspace_id)
    vocabulary = _load_published_vocabulary(
        uow_factory,
        workspace_id=workspace_id,
    )
    llm = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity.LARGE,
        streaming=False,
        # 산문 호출은 추출 호출보다 오래 걸려 기본 읽기 제한시간을 넘긴다.
        # CLI 러너와 같은 값을 준다.
        read_timeout=_NARRATION_READ_TIMEOUT_SECONDS,
    ).get_llm()
    extraction_spec = ExtractionRunSpec(
        provider=LlmProvider.AWS_BEDROCK.value,
        extractor_version=f"{CONTRACT_ID}/{_EXTRACTION_CONTRACT_VERSION}",
        ontology_id=CONTRACT_ID,
        vocabulary=vocabulary,
        model=settings.AWS_BEDROCK_LARGE_MODEL,
        prompt_version=PROMPT_VERSION,
    )
    result = await run_pre_review_pipeline(
        poll_result,
        workspace_id=workspace_id,
        normalizer=ChannelTalkUserChatNormalizer(),
        extractor=StructuredKnowledgeExtractor(llm),
        extraction_spec=extraction_spec,
        extraction_contract_version=_EXTRACTION_CONTRACT_VERSION,
        judge=BedrockIdentityJudge(
            llm,
            entity_types=vocabulary.entity_type_entries,
        ),
        uow_factory=uow_factory,
        # 임베더 없이 돌면 해소가 정확 일치 후보군으로 좁아져, 표기가 조금
        # 다른 같은 대상이 각자 노드로 굳는다. 한 번 굳으면 이 단계가 다시
        # 합쳐 주지 않으므로 만들지 못하면 그대로 실패시킨다.
        name_embedder=_name_embedder(workspace_id),
        # 산문 층은 CLI 러너와 같은 구성으로 붙인다. 빠지면 카드가 뼈대만
        # 남는다.
        narrator=LlmBlockNarrator(llm),
        # kill switch를 읽는 자리는 이 진입부 한 곳이다. 파이프라인과 해소
        # 서비스는 설정을 직접 읽지 않고 넘겨받은 값만 본다.
        auto_merge_enabled=settings.KNOWLEDGE_AUTO_MERGE_ENABLED,
    )
    if result.status is PreReviewPipelineStatus.PARTIAL_FAILURE:
        logger.warning(
            "knowledge_maintenance.channel_talk_job.partial_failure",
            setting_id=setting_id,
            workspace_id=workspace_id,
        )
    client = get_langfuse_client()
    if client is not None:
        try:
            await run_in_threadpool(client.flush)
        except Exception as error:
            logger.warning(
                "knowledge_maintenance.channel_talk_job.langfuse_flush_failed",
                error=str(error),
            )
    return result


def _derive_lookback_start(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    channel_id: str,
    now: Callable[[], datetime] | None = None,
) -> datetime:
    with session_factory() as db:
        latest = db.scalar(
            select(func.max(SourceVersionRow.source_updated_at)).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.source_type == "channel_talk",
                SourceVersionRow.entity_type == "user_chat",
                SourceVersionRow.scope_id == channel_id,
            )
        )
    if latest is not None:
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return latest.astimezone(timezone.utc) - timedelta(
            minutes=_LOOKBACK_OVERLAP_MINUTES
        )
    current = (now or _utcnow)()
    return current - timedelta(days=_BACKFILL_DAYS)


def _load_published_vocabulary(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    workspace_id: int,
) -> ExtractionVocabulary:
    with uow_factory() as uow:
        version = resolve_latest_published_version(
            uow.ontology.list_versions(
                workspace_id=workspace_id,
                ontology_id=CONTRACT_ID,
            )
        )
        vocabulary = (
            uow.ontology.get(
                workspace_id=workspace_id,
                ontology_id=CONTRACT_ID,
                version=version,
            )
            if version is not None
            else None
        )
    if vocabulary is None:
        raise RuntimeError(
            f"Published knowledge vocabulary not found for workspace {workspace_id}"
        )
    return vocabulary


def _name_embedder(workspace_id: int) -> NameEmbedder:
    """캐시를 두른 이름 임베더를 만든다.

    캐시가 있으면 이미 벡터로 바꿔 본 이름은 다시 임베딩하지 않는다.
    라운드마다 살아 있는 노드 별칭을 전부 다시 부르던 몫이 줄어든다.
    """
    return cached_name_embedder(
        EmbeddingServiceNameEmbedder(
            get_embedding_service(EmbeddingProvider.AWS_BEDROCK)
        ),
        SqlAlchemyNameEmbeddingCache(SessionLocal),
        workspace_id=workspace_id,
    )


def _uow_factory(
    workspace_id: int,
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(
        SessionLocal,
        workspace_id=workspace_id,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
