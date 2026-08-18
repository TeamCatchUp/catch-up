"""LLM Wiki의 채널·폴더 관리 HTTP 엔드포인트를 정의한다.

인가가 두 겹인 것은 검수 API와 같지만 첫 겹이 다르다. 표면에 서는 자격은
소속뿐이다(`resolve_member_workspace`) — 채널이 하나도 없는 사람이 첫
채널을 만들 수 있어야 하는데, 검수 자격 게이트를 쓰면 역할이 없어 문
앞에서 막힌다. 대상이 정해지는 핸들러가 "이 채널의 관리자인가"를 다시
본다.

관리자 판정의 출처는 `load_wiki_roles`의 `admin_channel_ids` 하나다.
핸들러마다 channel_admins를 따로 조회하면 검수 쪽 판정과 규칙이 갈릴
자리가 생긴다.

쓰기는 세션으로 직접 한다. 채널·폴더는 불변식이랄 것이 UNIQUE 두 개뿐이라
도메인 서비스를 세울 규모가 아니다. UNIQUE 위반은 예외 문자열을 읽지 않고
제약 이름으로 갈라 409로 옮긴다 — 문구를 파싱하면 드라이버가 문구를 다듬는
순간 계약이 깨진다.

거부는 전부 `deny_reviewer`를 지난다. 막힌 시도가 감사 스트림에 남아야
"누가 남의 채널을 만지려 했나"를 나중에 물을 수 있고, 검수 API와 같은
채널·같은 모양으로 모여야 그 질문이 한 번에 끝난다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import Response
from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import KnowledgeReviewAuditMetadata
from catchup.auth.dependencies import require_admin_user
from catchup.db import wiki as wiki_queries
from catchup.db.dependencies import get_db
from catchup.db.models import Channel
from catchup.db.models import ChannelFolder
from catchup.db.models import ChannelTalkCredentials
from catchup.db.models import KnowledgeArtifact
from catchup.db.test_knowledge_maintenance_settings import (
    list_test_knowledge_maintenance_settings,
)
from catchup.db.test_knowledge_maintenance_settings import (
    upsert_test_knowledge_maintenance_setting,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.session_bound import (
    SessionBoundOntologyUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact_definition import (
    serialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.preset_catalog import PRESET_DOMAINS
from catchup.knowledge_maintenance.domain.preset_catalog import PRESET_STYLES
from catchup.knowledge_maintenance.domain.preset_catalog import find_kind
from catchup.knowledge_maintenance.domain.preset_catalog import find_purpose
from catchup.knowledge_maintenance.domain.preset_catalog import find_style
from catchup.knowledge_maintenance.services.install_seed_vocabulary import (
    install_seed_vocabulary,
)
from catchup.observability.logging import get_logger
from catchup.server.wiki.dependencies import MemberContext
from catchup.server.wiki.dependencies import deny_reviewer
from catchup.server.wiki.dependencies import resolve_member_workspace
from catchup.server.wiki.dependencies import review_error
from catchup.server.wiki.owners import owners_by_artifact
from catchup.server.wiki.roles import can_manage_owners
from catchup.server.wiki.roles import load_wiki_roles
from catchup.server.wiki.schemas import ArtifactBlockSourceResponse
from catchup.server.wiki.schemas import ArtifactDocumentBlockResponse
from catchup.server.wiki.schemas import ArtifactDocumentResponse
from catchup.server.wiki.schemas import ArtifactListItemResponse
from catchup.server.wiki.schemas import ArtifactListResponse
from catchup.server.wiki.schemas import ArtifactLocationResponse
from catchup.server.wiki.schemas import ArtifactMoveRequest
from catchup.server.wiki.schemas import ArtifactOwnerResponse
from catchup.server.wiki.schemas import ChannelAdminResponse
from catchup.server.wiki.schemas import ChannelCreateRequest
from catchup.server.wiki.schemas import ChannelListItemResponse
from catchup.server.wiki.schemas import ChannelListResponse
from catchup.server.wiki.schemas import ChannelOnboardingRequest
from catchup.server.wiki.schemas import ChannelOnboardingResponse
from catchup.server.wiki.schemas import ChannelRenameRequest
from catchup.server.wiki.schemas import ChannelResponse
from catchup.server.wiki.schemas import DefinitionPresetsResponse
from catchup.server.wiki.schemas import DefinitionSummaryResponse
from catchup.server.wiki.schemas import FavoriteItemResponse
from catchup.server.wiki.schemas import FavoriteListResponse
from catchup.server.wiki.schemas import FavoriteResponse
from catchup.server.wiki.schemas import FolderCreateRequest
from catchup.server.wiki.schemas import FolderRenameRequest
from catchup.server.wiki.schemas import FolderResponse
from catchup.server.wiki.schemas import LatestRevisionResponse
from catchup.server.wiki.schemas import OwnerResponse
from catchup.server.wiki.schemas import PresetDomainResponse
from catchup.server.wiki.schemas import PresetKindResponse
from catchup.server.wiki.schemas import PresetPurposeResponse
from catchup.server.wiki.schemas import PresetStyleResponse
from catchup.server.wiki.schemas import TestKnowledgeMaintenanceSettingListResponse
from catchup.server.wiki.schemas import TestKnowledgeMaintenanceSettingRequest
from catchup.server.wiki.schemas import TestKnowledgeMaintenanceSettingResponse
from catchup.utils.scheduler import apply_test_knowledge_maintenance_schedule

router = APIRouter(
    prefix="/api/v1/wiki",
    tags=["Wiki Channels"],
)

logger = get_logger(__name__)

_CHANNEL_NAME_CONSTRAINT = "uq_channels_workspace_name"
_FOLDER_NAME_CONSTRAINT = "uq_channel_folders_channel_name"
_ARTIFACT_FOLDER_CONSTRAINT = "fk_knowledge_artifacts_folder"
_OWNER_PK_CONSTRAINT = "artifact_owners_pkey"
_ADMIN_PK_CONSTRAINT = "channel_admins_pkey"


def _purposes_for_kind(purpose_ids: list[str], kind: str) -> list[str]:
    """채널의 목적 preset 중 이 문서 종류를 권하는 것만 골라 돌려준다.

    정의 행에는 목적 preset id를 저장하지 않는다. 목적과 문서 종류의 짝은
    카탈로그가 이미 알고 있어(`PresetPurpose.recommended_kind`), 저장해 두면
    카탈로그가 바뀔 때 두 값이 어긋난다. 그래서 읽을 때 계산한다.
    """
    matched = []
    for purpose_id in purpose_ids:
        found = find_purpose(purpose_id)
        if found is not None and found[1].recommended_kind == kind:
            matched.append(purpose_id)

    return matched


def _violates(error: IntegrityError, constraint: str) -> bool:
    """이 IntegrityError가 그 제약을 어긴 것인지 본다.

    psycopg가 실어 주는 제약 이름만 본다. 없으면 False로 두어 알 수 없는
    위반을 409로 둔갑시키지 않는다 — 그 경우는 500으로 나가 사람이 보게
    하는 편이 낫다.
    """
    constraint_name = getattr(
        getattr(error.orig, "diag", None), "constraint_name", None
    )
    return constraint_name == constraint


def _load_channel(
    db: Session, *, channel_id: uuid.UUID, workspace_id: int
) -> Channel:
    """이 workspace의 채널 하나를 읽는다.

    다른 workspace의 채널은 없는 것으로 답한다. 403으로 가르면 남의
    workspace에 어떤 채널이 있는지를 이 응답으로 떠볼 수 있다.

    Raises:
        HTTPException: 채널이 없으면 404를 던진다.
    """
    channel = wiki_queries.get_channel(
        db, channel_id=channel_id, workspace_id=workspace_id
    )
    if channel is None:
        raise review_error(
            404,
            code="CHANNEL_NOT_FOUND",
            message="채널을 찾을 수 없습니다.",
        )
    return channel


def _require_channel_admin(
    db: Session, *, channel_id: uuid.UUID, context: MemberContext
) -> Channel:
    """채널을 읽고 그 채널의 관리자인지 확인한다.

    존재 확인이 먼저다. 없는 채널에 403을 주면 소비자는 권한 문제로 읽고
    관리자에게 문의하러 간다.

    Raises:
        HTTPException: 채널이 없으면 404, 관리자가 아니면 403을 던진다.
    """
    channel = _load_channel(
        db, channel_id=channel_id, workspace_id=context.workspace_id
    )
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    if channel.id not in roles.admin_channel_ids:
        raise deny_reviewer(
            403,
            code="NOT_CHANNEL_ADMIN",
            message="이 채널의 관리자가 아닙니다.",
            user_id=context.user.id,
            workspace_id=context.workspace_id,
        )
    return channel


def _load_folder(
    db: Session, *, folder_id: uuid.UUID, channel_id: uuid.UUID
) -> ChannelFolder:
    """그 채널에 달린 폴더 하나를 읽는다.

    channel_id를 조건에 함께 넣는다. 폴더 id만으로 찾으면 A 채널 관리자가
    경로에 자기 채널을 적고 B 채널의 폴더 id를 실어 남의 폴더를 지울 수
    있다.

    Raises:
        HTTPException: 폴더가 없거나 그 채널의 것이 아니면 404를 던진다.
    """
    folder = wiki_queries.get_folder(
        db, folder_id=folder_id, channel_id=channel_id
    )
    if folder is None:
        raise review_error(
            404,
            code="FOLDER_NOT_FOUND",
            message="폴더를 찾을 수 없습니다.",
        )
    return folder


def _reject_folder(
    db: Session, *, folder_id: uuid.UUID, workspace_id: int
) -> None:
    """그 채널에 없는 폴더를 두 갈래로 갈라 거절한다.

    다른 채널에 있는 폴더는 422(고른 폴더가 틀렸다), 아예 없는 폴더는
    404(폴더가 사라졌다)다. 한 코드로 묶으면 소비자가 두 상황에 같은 화면을
    내게 된다.

    다른 workspace의 폴더는 없는 것으로 답한다. 422로 가르면 응답만으로 남의
    workspace에 그 폴더가 있는지를 떠볼 수 있다.

    Raises:
        HTTPException: 늘 422 또는 404를 던진다.
    """
    folder = wiki_queries.get_folder_any(db, folder_id=folder_id)
    if folder is not None and folder.workspace_id == workspace_id:
        raise review_error(
            422,
            code="FOLDER_CHANNEL_MISMATCH",
            message="문서가 놓인 채널의 폴더가 아닙니다.",
        )
    raise review_error(
        404,
        code="FOLDER_NOT_FOUND",
        message="폴더를 찾을 수 없습니다.",
    )


def _load_artifact(
    db: Session, *, artifact_id: uuid.UUID, workspace_id: int
) -> KnowledgeArtifact:
    """이 workspace의 문서 한 편을 읽는다.

    다른 workspace의 문서는 없는 것으로 답한다. 채널과 같은 이유다 —
    403으로 가르면 응답만으로 남의 workspace에 그 문서가 있는지를 떠볼 수
    있다.

    Raises:
        HTTPException: 문서가 없으면 404를 던진다.
    """
    artifact = wiki_queries.get_artifact(
        db, artifact_id=artifact_id, workspace_id=workspace_id
    )
    if artifact is None:
        raise review_error(
            404,
            code="ARTIFACT_NOT_FOUND",
            message="문서를 찾을 수 없습니다.",
        )
    return artifact


def _require_workspace_member(
    db: Session, *, user_id: int, workspace_id: int
) -> None:
    """지정 대상이 이 workspace 구성원인지 확인한다.

    소속 밖 사람에게 역할을 주면 그 사람은 검수 표면에는 서지 못하면서
    역할 행만 남아, 담당자가 있는데 아무도 결정하지 못하는 문서가 된다.
    권한 문제가 아니라 요청 자체가 성립하지 않는 경우라 400이다.

    Raises:
        HTTPException: 대상이 구성원이 아니면 400을 던진다.
    """
    membership = wiki_queries.get_workspace_membership_user_id(
        db, user_id=user_id, workspace_id=workspace_id
    )
    if membership is None:
        raise review_error(
            400,
            code="USER_NOT_MEMBER",
            message="대상 사용자가 이 워크스페이스의 구성원이 아닙니다.",
        )


def _load_channel_admin_ids(
    db: Session, channel_id: uuid.UUID
) -> list[int]:
    """채널 관리자 명단을 정렬된 순서로 읽는다."""
    return sorted(wiki_queries.list_channel_admin_ids(db, channel_id))


@router.get(
    path="/knowledge-maintenance-settings",
    response_model=TestKnowledgeMaintenanceSettingListResponse,
    dependencies=[Depends(require_admin_user)],
)
def list_knowledge_maintenance_settings(
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> TestKnowledgeMaintenanceSettingListResponse:
    return TestKnowledgeMaintenanceSettingListResponse(
        items=[
            TestKnowledgeMaintenanceSettingResponse.model_validate(setting)
            for setting in list_test_knowledge_maintenance_settings(
                db,
                workspace_id=context.workspace_id,
            )
        ]
    )


@router.put(
    path="/knowledge-maintenance-settings/{channel_talk_credential_id}",
    response_model=TestKnowledgeMaintenanceSettingResponse,
    dependencies=[Depends(require_admin_user)],
)
def update_knowledge_maintenance_setting(
    channel_talk_credential_id: int,
    payload: TestKnowledgeMaintenanceSettingRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> TestKnowledgeMaintenanceSettingResponse:
    if db.get(ChannelTalkCredentials, channel_talk_credential_id) is None:
        raise review_error(
            404,
            code="CHANNEL_TALK_CREDENTIAL_NOT_FOUND",
            message="ChannelTalk 연결 정보를 찾을 수 없습니다.",
        )
    try:
        setting = upsert_test_knowledge_maintenance_setting(
            db,
            workspace_id=context.workspace_id,
            channel_talk_credential_id=channel_talk_credential_id,
            enabled=payload.enabled,
            execution_anchor_at=payload.execution_anchor_at,
            interval_minutes=payload.interval_minutes,
        )
        db.commit()
        db.refresh(setting)
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception(
            "test_knowledge_maintenance_setting_update_failed",
            workspace_id=context.workspace_id,
            channel_talk_credential_id=channel_talk_credential_id,
        )
        raise review_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="KNOWLEDGE_MAINTENANCE_SETTING_UPDATE_FAILED",
            message="지식 유지보수 설정을 저장하지 못했습니다.",
        ) from error

    try:
        apply_test_knowledge_maintenance_schedule(setting)
    except Exception as error:
        logger.exception(
            "test_knowledge_maintenance_schedule_apply_failed",
            setting_id=setting.id,
            workspace_id=context.workspace_id,
        )
        raise review_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="KNOWLEDGE_MAINTENANCE_SCHEDULE_NOT_APPLIED",
            message="설정은 저장했지만 실행 중인 스케줄에 반영하지 못했습니다.",
        ) from error
    return TestKnowledgeMaintenanceSettingResponse.model_validate(setting)


@router.post(
    path="/channels",
    response_model=ChannelResponse,
    status_code=201,
    description="위키 채널을 만들고 생성자를 그 채널의 관리자로 세운다.",
)
def create_channel(
    request: ChannelCreateRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelResponse:
    """채널을 만들고 생성자를 관리자로 세운다.

    채널 INSERT와 관리자 INSERT는 한 트랜잭션이다. 나뉘면 관리자가 없는
    채널이 남아, 만든 사람조차 이름을 못 바꾸는 상태가 된다.

    Raises:
        HTTPException: 같은 workspace에 같은 이름이 있으면 409를 던진다.
    """
    channel = wiki_queries.add_channel(
        db,
        workspace_id=context.workspace_id,
        name=request.name,
        created_by=context.user.id,
    )
    try:
        db.flush()
        wiki_queries.add_channel_admin(
            db,
            channel_id=channel.id,
            user_id=context.user.id,
            granted_by=context.user.id,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _CHANNEL_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="CHANNEL_NAME_TAKEN",
                message="같은 이름의 채널이 이미 있습니다.",
            ) from error
        raise

    return ChannelResponse(
        id=str(channel.id),
        name=channel.name,
        workspace_id=channel.workspace_id,
    )


@router.post(
    path="/channels/onboarding",
    response_model=ChannelOnboardingResponse,
    status_code=201,
    description="preset 선택으로 채널·관리자·목적·정의·폴더·seed 어휘를 만든다.",
)
def onboard_channel(
    request: ChannelOnboardingRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelOnboardingResponse:
    """preset 선택으로 채널·관리자·목적·정의·폴더·seed 어휘를 한 번에 만든다.

    전부 한 트랜잭션이다. 나뉘면 관리자 없는 채널이나 정의 없는 채널이
    남아, 온보딩을 끝낸 사람이 아무것도 못 하는 자리가 생긴다.

    고른 문서 종류마다 정의 하나와 폴더 하나를 만든다. 폴더 이름은 그
    종류의 라벨을 그대로 쓴다. 같은 이름의 폴더가 이미 있으면 새로 만들지
    않고 그것을 다시 쓴다. (channel_id, name)이 UNIQUE라 두 번 만들면
    INSERT가 막힌다.

    정의를 만들 때 어휘를 검증하지 않는다. 선택 규칙이 가리키는 이름이
    아직 사전에 없어도 정의는 그대로 선다. 검증은 컴파일 시점의 일이고,
    그때의 skip과 경고가 아직 안 모인 이름을 기다려 준다. 입구에서 막으면
    어휘가 자라기 전에는 채널을 세울 수 없다.

    Raises:
        HTTPException: 카탈로그에 없는 preset이면 422, 같은 workspace에
            같은 이름의 채널이 있으면 409를 던진다.
    """
    domain = next(
        (item for item in PRESET_DOMAINS if item.id == request.domain_preset),
        None,
    )
    if domain is None:
        raise review_error(
            422,
            code="UNKNOWN_DOMAIN",
            message="카탈로그에 없는 도메인 preset입니다.",
        )

    purposes = []
    for purpose_id in request.purpose_presets:
        found = find_purpose(purpose_id)
        if found is None or found[0].id != domain.id:
            raise review_error(
                422,
                code="UNKNOWN_PURPOSE",
                message="이 도메인에 없는 목적 preset입니다.",
            )
        purposes.append(found[1])

    if find_style(request.style_preset) is None:
        raise review_error(
            422,
            code="UNKNOWN_STYLE",
            message="카탈로그에 없는 문체 preset입니다.",
        )

    preset_kinds = []
    # 같은 종류를 두 번 골라도 정의는 하나다. 고른 순서는 그대로 둔다.
    for kind in dict.fromkeys(request.kinds):
        preset_kind = find_kind(domain, kind)
        if preset_kind is None:
            raise review_error(
                422,
                code="UNKNOWN_KIND",
                message="이 도메인에 없는 문서 종류입니다.",
            )
        preset_kinds.append(preset_kind)

    channel = wiki_queries.add_channel(
        db,
        workspace_id=context.workspace_id,
        name=request.name,
        created_by=context.user.id,
        style_preset=request.style_preset,
    )
    try:
        db.flush()
        wiki_queries.add_channel_admin(
            db,
            channel_id=channel.id,
            user_id=context.user.id,
            granted_by=context.user.id,
        )
        wiki_queries.add_channel_purposes(
            db,
            channel_id=channel.id,
            purpose_presets=[purpose.id for purpose in purposes],
        )
        created = []
        for preset_kind in preset_kinds:
            folder = wiki_queries.get_folder_by_name(
                db, channel_id=channel.id, name=preset_kind.label
            )
            if folder is None:
                folder = wiki_queries.add_folder(
                    db,
                    workspace_id=context.workspace_id,
                    channel_id=channel.id,
                    name=preset_kind.label,
                )
                db.flush()
            kind_purposes = [
                purpose
                for purpose in purposes
                if purpose.recommended_kind == preset_kind.kind
            ]
            purpose_text = (
                " ".join(
                    f"이 문서의 목적은 '{purpose.label}'이다."
                    for purpose in kind_purposes
                )
                or None
            )
            definition = wiki_queries.add_artifact_definition(
                db,
                workspace_id=context.workspace_id,
                channel_id=channel.id,
                kind=preset_kind.kind,
                selection_spec=serialize_selection_spec(
                    preset_kind.spec_template()
                ),
                created_by=context.user.id,
                folder_id=folder.id,
                purpose=purpose_text,
            )
            created.append((definition, folder, kind_purposes))
        db.flush()
        vocabulary_version = install_seed_vocabulary(
            SessionBoundOntologyUnitOfWork(db),
            workspace_id=context.workspace_id,
            seed=domain.seed_vocabulary,
            ontology_id=CONTRACT_ID,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _CHANNEL_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="CHANNEL_NAME_TAKEN",
                message="같은 이름의 채널이 이미 있습니다.",
            ) from error
        raise

    return ChannelOnboardingResponse(
        channel=ChannelResponse(
            id=str(channel.id),
            name=channel.name,
            workspace_id=channel.workspace_id,
        ),
        domain_preset=domain.id,
        purpose_presets=[purpose.id for purpose in purposes],
        style_preset=request.style_preset,
        vocabulary_version=vocabulary_version,
        definitions=[
            DefinitionSummaryResponse(
                definition_id=str(definition.id),
                kind=definition.kind,
                folder_id=str(folder.id),
                purpose_presets=[purpose.id for purpose in kind_purposes],
            )
            for definition, folder, kind_purposes in created
        ],
    )


@router.get(
    path="/channels",
    response_model=ChannelListResponse,
    description="이 workspace의 채널을 폴더·문서 수와 함께 조회한다.",
)
def list_channels(
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelListResponse:
    """채널 목록을 폴더 목록·문서 수와 함께 돌려준다.

    구성원이면 workspace의 채널을 전부 본다. 목록을 관리 범위로 좁히는
    일은 이 슬라이스 밖이다 — 채널은 읽는 자리를 고르는 색인이라, 보이지
    않으면 문서를 찾을 길이 없다.
    """
    channels = wiki_queries.list_channels(db, context.workspace_id)
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )

    folders: dict[uuid.UUID, list[FolderResponse]] = {}
    for folder in wiki_queries.list_folders(db, context.workspace_id):
        folders.setdefault(folder.channel_id, []).append(
            FolderResponse(
                id=str(folder.id),
                name=folder.name,
                channel_id=str(folder.channel_id),
            )
        )

    counts = wiki_queries.count_artifacts_by_channel(
        db, context.workspace_id
    )
    purposes = wiki_queries.list_channel_purposes_by_workspace(
        db, context.workspace_id
    )
    definitions = wiki_queries.list_definitions_by_workspace(
        db, context.workspace_id
    )

    return ChannelListResponse(
        channels=[
            ChannelListItemResponse(
                id=str(channel.id),
                name=channel.name,
                workspace_id=channel.workspace_id,
                is_admin=channel.id in roles.admin_channel_ids,
                document_count=counts.get(channel.id, 0),
                folders=folders.get(channel.id, []),
                purpose_presets=purposes.get(channel.id, []),
                definitions=[
                    DefinitionSummaryResponse(
                        definition_id=str(definition.id),
                        kind=definition.kind,
                        folder_id=(
                            str(definition.folder_id)
                            if definition.folder_id is not None
                            else None
                        ),
                        purpose_presets=_purposes_for_kind(
                            purposes.get(channel.id, []), definition.kind
                        ),
                    )
                    for definition in definitions.get(channel.id, [])
                ],
            )
            for channel in channels
        ]
    )


@router.get(
    path="/definition-presets",
    response_model=DefinitionPresetsResponse,
    description="온보딩이 고를 도메인·목적·문서 종류·문체를 조회한다.",
)
def list_definition_presets(
    context: MemberContext = Depends(resolve_member_workspace),
) -> DefinitionPresetsResponse:
    """preset 카탈로그를 그대로 옮겨 돌려준다.

    DB를 읽지 않는다. 카탈로그는 코드 안의 상수라 workspace마다 달라질
    것이 없고, 인가는 구성원인지만 본다.

    선택 규칙과 seed 어휘는 빼고 담는다. 화면이 쓰지 않는 값인데다,
    규칙을 내보내면 소비자가 그것을 되돌려 보낼 입구가 생긴다.
    """
    return DefinitionPresetsResponse(
        domains=[
            PresetDomainResponse(
                id=domain.id,
                label=domain.label,
                purposes=[
                    PresetPurposeResponse(
                        id=purpose.id,
                        label=purpose.label,
                        recommended_kind=purpose.recommended_kind,
                    )
                    for purpose in domain.purposes
                ],
                kinds=[
                    PresetKindResponse(
                        kind=preset_kind.kind,
                        label=preset_kind.label,
                        description=preset_kind.description,
                        example_text=preset_kind.example_text,
                    )
                    for preset_kind in domain.kinds
                ],
            )
            for domain in PRESET_DOMAINS
        ],
        styles=[
            PresetStyleResponse(id=style.id, label=style.label)
            for style in PRESET_STYLES
        ],
    )


@router.patch(
    path="/channels/{channel_id}",
    response_model=ChannelResponse,
    description="채널 이름을 바꾼다. 그 채널의 관리자만 할 수 있다.",
)
def rename_channel(
    channel_id: uuid.UUID,
    request: ChannelRenameRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelResponse:
    """채널 이름을 바꾼다.

    Raises:
        HTTPException: 채널이 없으면 404, 관리자가 아니면 403, 같은 이름이
            이미 있으면 409를 던진다.
    """
    channel = _require_channel_admin(
        db, channel_id=channel_id, context=context
    )
    channel.name = request.name
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _CHANNEL_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="CHANNEL_NAME_TAKEN",
                message="같은 이름의 채널이 이미 있습니다.",
            ) from error
        raise

    return ChannelResponse(
        id=str(channel.id),
        name=channel.name,
        workspace_id=channel.workspace_id,
    )


@router.post(
    path="/channels/{channel_id}/folders",
    response_model=FolderResponse,
    status_code=201,
    description="채널 바로 아래에 폴더를 만든다. 관리자만 할 수 있다.",
)
def create_folder(
    channel_id: uuid.UUID,
    request: FolderCreateRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> FolderResponse:
    """폴더를 만든다.

    workspace_id는 요청이 아니라 채널에서 읽어 채운다. 폴더는 채널과
    (workspace_id, channel_id) 복합 FK로 묶여 있어, 소비자가 준 값을
    믿으면 FK가 깨지거나 남의 workspace 아래에 폴더가 선다.

    Raises:
        HTTPException: 채널이 없으면 404, 관리자가 아니면 403, 같은 이름이
            이미 있으면 409를 던진다.
    """
    channel = _require_channel_admin(
        db, channel_id=channel_id, context=context
    )
    folder = wiki_queries.add_folder(
        db,
        workspace_id=channel.workspace_id,
        channel_id=channel.id,
        name=request.name,
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _FOLDER_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="FOLDER_NAME_TAKEN",
                message="같은 이름의 폴더가 이미 있습니다.",
            ) from error
        raise

    return FolderResponse(
        id=str(folder.id),
        name=folder.name,
        channel_id=str(folder.channel_id),
    )


@router.patch(
    path="/channels/{channel_id}/folders/{folder_id}",
    response_model=FolderResponse,
    description="폴더 이름을 바꾼다. 채널 관리자만 할 수 있다.",
)
def rename_folder(
    channel_id: uuid.UUID,
    folder_id: uuid.UUID,
    request: FolderRenameRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> FolderResponse:
    """폴더 이름을 바꾼다.

    Raises:
        HTTPException: 채널·폴더가 없으면 404, 관리자가 아니면 403, 같은
            이름이 이미 있으면 409를 던진다.
    """
    _require_channel_admin(db, channel_id=channel_id, context=context)
    folder = _load_folder(db, folder_id=folder_id, channel_id=channel_id)
    folder.name = request.name
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _FOLDER_NAME_CONSTRAINT):
            raise review_error(
                409,
                code="FOLDER_NAME_TAKEN",
                message="같은 이름의 폴더가 이미 있습니다.",
            ) from error
        raise

    return FolderResponse(
        id=str(folder.id),
        name=folder.name,
        channel_id=str(folder.channel_id),
    )


@router.delete(
    path="/channels/{channel_id}/folders/{folder_id}",
    status_code=204,
    description="폴더를 지운다. 채널 관리자만 할 수 있다.",
)
def delete_folder(
    channel_id: uuid.UUID,
    folder_id: uuid.UUID,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> Response:
    """폴더를 지운다.

    문서가 든 폴더는 지우지 못한다. 문서가 딸린 FK는 RESTRICT라 DB가
    삭제를 막는데, 그 위반을 잡지 않으면 이 경로만 500으로 나가
    `{"code", "message"}` 계약이 깨진다. "먼저 문서를 옮기라"는 사실을
    소비자가 코드로 읽을 수 있어야 화면이 다음 할 일을 안내한다.

    Raises:
        HTTPException: 채널·폴더가 없으면 404, 관리자가 아니면 403,
            폴더에 문서가 남아 있으면 409를 던진다.
    """
    _require_channel_admin(db, channel_id=channel_id, context=context)
    folder = _load_folder(db, folder_id=folder_id, channel_id=channel_id)
    wiki_queries.remove_folder(db, folder)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _violates(error, _ARTIFACT_FOLDER_CONSTRAINT):
            raise review_error(
                409,
                code="FOLDER_NOT_EMPTY",
                message="문서가 있는 폴더는 삭제할 수 없습니다."
                " 문서를 먼저 옮겨 주세요.",
            ) from error
        raise

    return Response(status_code=204)


def _to_list_item(
    row: wiki_queries.ArtifactListRow,
    *,
    owners: list[OwnerResponse],
    is_favorite: bool,
) -> ArtifactListItemResponse:
    """문서 목록 한 줄을 응답 모양으로 옮겨 담는다."""
    latest = None
    if row.latest_revision_id is not None:
        latest = LatestRevisionResponse(
            revision_id=str(row.latest_revision_id),
            revision_number=row.latest_revision_number or 0,
            published_at=row.latest_published_at,
        )
    return ArtifactListItemResponse(
        artifact_id=str(row.artifact_id),
        kind=row.kind,
        title=row.title,
        channel_id=None if row.channel_id is None else str(row.channel_id),
        folder_id=None if row.folder_id is None else str(row.folder_id),
        created_at=row.created_at,
        status=wiki_queries.artifact_status(row),
        pending_proposal_count=row.pending_proposal_count,
        latest_revision=latest,
        owners=owners,
        is_favorite=is_favorite,
    )


@router.get(
    path="/artifacts",
    response_model=ArtifactListResponse,
    description="이 workspace의 문서를 상태·담당자·즐겨찾기와 함께 조회한다.",
)
def list_artifacts(
    channel_id: uuid.UUID | None = Query(None),
    folder_id: uuid.UUID | None = Query(None),
    kind: str | None = Query(None),
    status_filter: (
        Literal["pending_review", "published", "no_revision"] | None
    ) = Query(None, alias="status"),
    owner_user_id: int | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ArtifactListResponse:
    """문서 목록 한 쪽을 상태·담당자·즐겨찾기와 함께 돌려준다.

    담당자와 즐겨찾기는 줄마다 따로 묻지 않고 한 번에 읽어 붙인다. 줄 수만큼
    질의가 늘면 목록 한 장을 그리는 비용이 문서 수에 비례해 커진다.

    total은 limit·offset을 걸기 전의 수다. 이 쪽에 실린 개수로는 소비자가
    쪽 수를 계산할 수 없다.
    """
    rows, total = wiki_queries.list_artifacts(
        db,
        workspace_id=context.workspace_id,
        channel_id=channel_id,
        folder_id=folder_id,
        kind=kind,
        status=status_filter,
        owner_user_id=owner_user_id,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )
    artifact_ids = [row.artifact_id for row in rows]
    owners = owners_by_artifact(db, artifact_ids)
    favorites = wiki_queries.list_favorite_artifact_ids(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    return ArtifactListResponse(
        items=[
            _to_list_item(
                row,
                owners=owners[row.artifact_id],
                is_favorite=row.artifact_id in favorites,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    path="/favorites",
    response_model=FavoriteListResponse,
    description="이 workspace에서 즐겨찾기한 문서를 최근에 담은 순으로 조회한다.",
)
def list_favorites(
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> FavoriteListResponse:
    """즐겨찾기한 문서를 최근에 담은 순으로 돌려준다."""
    rows = wiki_queries.list_favorites(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    return FavoriteListResponse(
        items=[
            FavoriteItemResponse(
                artifact_id=str(artifact.id),
                title=artifact.title,
                kind=artifact.kind,
                channel_id=(
                    None
                    if artifact.channel_id is None
                    else str(artifact.channel_id)
                ),
                folder_id=(
                    None
                    if artifact.folder_id is None
                    else str(artifact.folder_id)
                ),
                favorited_at=favorited_at,
            )
            for artifact, favorited_at in rows
        ]
    )


@router.put(
    path="/favorites/{artifact_id}",
    response_model=FavoriteResponse,
    description="문서를 즐겨찾기에 담는다. 이미 담겨 있어도 같은 결과다.",
)
def add_favorite(
    artifact_id: uuid.UUID,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> FavoriteResponse:
    """문서 하나를 즐겨찾기에 담는다.

    멱등이다. 이미 담겨 있어도 200으로 답한다 — 즐겨찾기는 있고 없고만
    의미가 있어, 결과 상태가 같은 두 번째 요청을 실패로 볼 이유가 없다.

    Raises:
        HTTPException: 이 workspace의 문서가 아니면 404를 던진다.
    """
    artifact = _load_artifact(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    wiki_queries.add_favorite(
        db,
        user_id=context.user.id,
        artifact_id=artifact.id,
        workspace_id=context.workspace_id,
    )
    try:
        db.commit()
    except IntegrityError:
        # 같은 문서를 동시에 담은 경우다. 결과 상태가 요청과 같으므로
        # 멱등 경로로 합류시킨다.
        db.rollback()

    return FavoriteResponse(artifact_id=str(artifact.id), is_favorite=True)


@router.delete(
    path="/favorites/{artifact_id}",
    status_code=204,
    description="문서를 즐겨찾기에서 뺀다. 담겨 있지 않아도 같은 결과다.",
)
def remove_favorite(
    artifact_id: uuid.UUID,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> Response:
    """문서 하나를 즐겨찾기에서 뺀다. 지정과 같은 이유로 멱등이다.

    Raises:
        HTTPException: 이 workspace의 문서가 아니면 404를 던진다.
    """
    artifact = _load_artifact(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    wiki_queries.remove_favorite(
        db, user_id=context.user.id, artifact_id=artifact.id
    )
    db.commit()

    return Response(status_code=204)


@router.get(
    path="/artifacts/{artifact_id}",
    response_model=ArtifactDocumentResponse,
    description="발행된 문서의 최신 판을 산문·근거와 함께 조회한다.",
)
def get_artifact_document(
    artifact_id: uuid.UUID,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ArtifactDocumentResponse:
    """지금 발행된 판의 블록을 산문·근거 인용과 함께 돌려준다.

    산문만 내보내지 않는다. 산문은 표현이고 근거 지위는 인용 원문에만
    있으므로, 둘을 갈라 내보내면 읽는 쪽이 문장을 근거와 대조할 길이
    없어진다.

    아직 발행된 판이 없으면 없는 것으로 답한다. 계류 중인 변경안은 사람이
    승인하지 않은 내용이라 읽기 표면에 실릴 자리가 아니고, 그것을 여기서
    보여 주면 검수 게이트를 우회하는 길이 된다.
    """
    artifact = _load_artifact(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    revision = wiki_queries.get_latest_revision(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    if revision is None:
        raise review_error(
            404,
            code="ARTIFACT_NOT_PUBLISHED",
            message="아직 발행된 판이 없습니다.",
        )
    return ArtifactDocumentResponse(
        artifact_id=str(artifact.id),
        channel_id=(
            None if artifact.channel_id is None else str(artifact.channel_id)
        ),
        definition_id=(
            None
            if artifact.definition_id is None
            else str(artifact.definition_id)
        ),
        kind=artifact.kind,
        title=artifact.title,
        folder_id=(
            None if artifact.folder_id is None else str(artifact.folder_id)
        ),
        owners=owners_by_artifact(db, [artifact.id])[artifact.id],
        is_favorite=wiki_queries.is_favorite(
            db, user_id=context.user.id, artifact_id=artifact.id
        ),
        revision_id=str(revision.id),
        published_at=revision.created_at,
        blocks=[
            ArtifactDocumentBlockResponse(
                block_index=index,
                block_kind=block.block_kind,
                heading=block.heading,
                narrative=block.narrative,
                body=block.body,
                claim_ids=[str(item) for item in block.claim_ids],
                relation_ids=[str(item) for item in block.relation_ids],
                sources=[
                    ArtifactBlockSourceResponse(
                        claim_id=str(source.claim_id),
                        statement=source.statement,
                        observed_at=source.observed_at,
                        citation_verified=source.citation_verified,
                    )
                    for source in block.sources
                ],
            )
            for index, block in enumerate(deserialize_blocks(revision.blocks))
        ],
    )


@router.patch(
    path="/artifacts/{artifact_id}",
    response_model=ArtifactLocationResponse,
    description="문서를 같은 채널 안의 다른 폴더로 옮긴다. 관리자 또는 담당자만 할 수 있다.",
)
def move_artifact(
    artifact_id: uuid.UUID,
    request: ArtifactMoveRequest,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ArtifactLocationResponse:
    """문서를 같은 채널 안의 폴더로 옮기거나 채널 루트로 올린다.

    폴더가 그 문서의 채널에 달린 것인지 여기서 본다. DB의 복합 FK는 문서와
    폴더가 같은 workspace인지까지만 보므로, 채널이 다른 폴더로 옮기는 배치를
    막는 자리는 이 문 하나뿐이다.

    같은 채널에 없는 폴더는 두 갈래로 갈라 답한다. 다른 채널에 있으면 422,
    아예 없으면 404다. 둘을 한 코드로 묶으면 소비자가 "폴더를 잘못 골랐다"와
    "폴더가 지워졌다"에 같은 화면을 내게 된다.

    Raises:
        HTTPException: 문서가 없으면 404, 옮길 자격이 없으면 403, 폴더가
            다른 채널의 것이면 422, 폴더가 없으면 404를 던진다.
    """
    artifact = _load_artifact(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    owner_user_ids = frozenset(
        wiki_queries.list_artifact_owner_ids(db, artifact.id)
    )
    if not can_manage_owners(
        roles,
        artifact_channel_id=artifact.channel_id,
        artifact_id=artifact.id,
        owner_user_ids=owner_user_ids,
        user_id=context.user.id,
        for_removal=False,
    ):
        raise deny_reviewer(
            403,
            code="NOT_DOCUMENT_REVIEWER",
            message="이 문서를 옮길 권한이 없습니다.",
            user_id=context.user.id,
            workspace_id=context.workspace_id,
        )

    if request.folder_id is not None:
        if artifact.channel_id is None:
            raise review_error(
                422,
                code="FOLDER_CHANNEL_MISMATCH",
                message="채널에 놓이지 않은 문서는 폴더에 넣을 수 없습니다.",
            )
        folder = wiki_queries.get_folder(
            db, folder_id=request.folder_id, channel_id=artifact.channel_id
        )
        if folder is None:
            _reject_folder(
                db,
                folder_id=request.folder_id,
                workspace_id=context.workspace_id,
            )

    wiki_queries.set_artifact_folder(
        db, artifact=artifact, folder_id=request.folder_id
    )
    db.commit()

    return ArtifactLocationResponse(
        artifact_id=str(artifact.id),
        channel_id=(
            None if artifact.channel_id is None else str(artifact.channel_id)
        ),
        folder_id=(
            None if artifact.folder_id is None else str(artifact.folder_id)
        ),
    )


@router.put(
    path="/artifacts/{artifact_id}/owners/{user_id}",
    response_model=ArtifactOwnerResponse,
    status_code=201,
    description="문서 담당자를 지정한다. 관리자 또는 그 문서 담당자만 할 수 있다.",
)
def assign_artifact_owner(
    artifact_id: uuid.UUID,
    user_id: int,
    response: Response,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ArtifactOwnerResponse:
    """담당자 한 명을 문서에 붙인다.

    멱등이다. 이미 담당자면 200으로, 새로 붙었으면 201로 답한다. 담당자
    지정은 화면에서 여러 사람이 동시에 누르는 종류의 조작이라, 두 번째
    요청이 409로 실패하면 소비자는 자기가 이긴 경우와 진 경우를 갈라야
    한다 — 결과 상태는 같은데 오류 처리만 늘어난다.

    Raises:
        HTTPException: 문서가 없으면 404, 명단을 고칠 자격이 없으면 403,
            대상이 구성원이 아니면 400을 던진다.
    """
    artifact = _load_artifact(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    owner_user_ids = frozenset(
        wiki_queries.list_artifact_owner_ids(db, artifact.id)
    )
    if not can_manage_owners(
        roles,
        artifact_channel_id=artifact.channel_id,
        artifact_id=artifact.id,
        owner_user_ids=owner_user_ids,
        user_id=context.user.id,
        for_removal=False,
    ):
        raise deny_reviewer(
            403,
            code="NOT_OWNER_MANAGER",
            message="이 문서의 담당자를 지정할 자격이 없습니다.",
            user_id=context.user.id,
            workspace_id=context.workspace_id,
        )
    _require_workspace_member(
        db, user_id=user_id, workspace_id=context.workspace_id
    )

    if user_id in owner_user_ids:
        response.status_code = 200
    else:
        wiki_queries.add_artifact_owner(
            db,
            artifact_id=artifact.id,
            user_id=user_id,
            granted_by=context.user.id,
        )
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            # 같은 사람을 동시에 지정한 경우다. 결과 상태가 요청과 같으므로
            # 멱등 경로로 합류시킨다.
            if _violates(error, _OWNER_PK_CONSTRAINT):
                response.status_code = 200
            else:
                raise

    return ArtifactOwnerResponse(
        artifact_id=str(artifact.id),
        owners=owners_by_artifact(db, [artifact.id])[artifact.id],
    )


@router.delete(
    path="/artifacts/{artifact_id}/owners/{user_id}",
    status_code=204,
    description="문서 담당자를 해제한다. 관리자만 할 수 있다.",
)
def remove_artifact_owner(
    artifact_id: uuid.UUID,
    user_id: int,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> Response:
    """담당자 한 명을 문서에서 뗀다.

    담당자 본인도 못 뗀다. 명단이 줄어드는 방향은 관리자만 지나고, 실제로
    줄어들었을 때 감사 이벤트를 하나 낸다. 거부만 감사에 남으면 스트림은
    "막힌 시도"만 담고 책임자가 사라진 사실은 담지 않는다.

    없는 담당자를 떼는 요청도 204다. 자격 확인은 이미 지났고 결과 상태가
    요청과 같으므로, 404로 가르면 소비자에게 "그 사람이 담당자였는가"만
    알려 주고 할 일은 늘어난다. 그 경우는 명단이 줄지 않았으므로 감사
    이벤트도 내지 않는다.

    Raises:
        HTTPException: 문서가 없으면 404, 관리자가 아니면 403을 던진다.
    """
    artifact = _load_artifact(
        db, artifact_id=artifact_id, workspace_id=context.workspace_id
    )
    roles = load_wiki_roles(
        db, user_id=context.user.id, workspace_id=context.workspace_id
    )
    if not can_manage_owners(
        roles,
        artifact_channel_id=artifact.channel_id,
        artifact_id=artifact.id,
        owner_user_ids=frozenset(
            wiki_queries.list_artifact_owner_ids(db, artifact.id)
        ),
        user_id=context.user.id,
        for_removal=True,
    ):
        raise deny_reviewer(
            403,
            code="NOT_OWNER_MANAGER",
            message="이 문서의 담당자를 해제할 자격이 없습니다.",
            user_id=context.user.id,
            workspace_id=context.workspace_id,
        )

    owner = wiki_queries.get_artifact_owner(
        db, artifact_id=artifact.id, user_id=user_id
    )
    if owner is not None:
        wiki_queries.remove_artifact_owner(db, owner)
        db.commit()
        emit_audit_event(
            action=KnowledgeReviewAction.OWNER_REMOVE,
            status=AuditStatus.SUCCESS,
            metadata=KnowledgeReviewAuditMetadata(
                workspace_id=context.workspace_id,
                user_id=context.user.id,
                artifact_id=str(artifact.id),
                target_user_id=user_id,
            ),
        )

    return Response(status_code=204)


@router.put(
    path="/channels/{channel_id}/admins/{user_id}",
    response_model=ChannelAdminResponse,
    status_code=201,
    description="채널 관리자를 추가 지정한다. 그 채널의 기존 관리자만 할 수 있다.",
)
def assign_channel_admin(
    channel_id: uuid.UUID,
    user_id: int,
    response: Response,
    context: MemberContext = Depends(resolve_member_workspace),
    db: Session = Depends(get_db),
) -> ChannelAdminResponse:
    """채널 관리자 한 명을 더 세운다.

    해제는 없다. 마지막 관리자를 뗀 채널은 아무도 고칠 수 없는 상태로
    남는데, 그 경계를 어떻게 막을지가 아직 기획으로 정해지지 않았다.
    지정만 열어 두면 그 상태에 빠질 길이 없다.

    Raises:
        HTTPException: 채널이 없으면 404, 그 채널의 관리자가 아니면 403,
            대상이 구성원이 아니면 400을 던진다.
    """
    channel = _require_channel_admin(
        db, channel_id=channel_id, context=context
    )
    _require_workspace_member(
        db, user_id=user_id, workspace_id=context.workspace_id
    )

    existing = wiki_queries.get_channel_admin(
        db, channel_id=channel.id, user_id=user_id
    )
    if existing is not None:
        response.status_code = 200
    else:
        wiki_queries.add_channel_admin(
            db,
            channel_id=channel.id,
            user_id=user_id,
            granted_by=context.user.id,
        )
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            if _violates(error, _ADMIN_PK_CONSTRAINT):
                response.status_code = 200
            else:
                raise

    return ChannelAdminResponse(
        channel_id=str(channel.id),
        user_ids=_load_channel_admin_ids(db, channel.id),
    )
