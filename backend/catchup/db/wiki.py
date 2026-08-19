"""LLM Wiki의 채널·폴더·역할 테이블에 대한 쿼리를 모은다.

전부 `db: Session`을 첫 인자로 받는 얇은 함수다. 판정도, 오류 변환도, HTTP
코드도 여기에는 없다 — 그것들은 server 계층의 몫이다. 이 모듈은 "무엇을
읽고 무엇을 넣는가"만 안다.

트랜잭션 경계는 호출자가 쥔다. flush·commit·rollback을 여기서 하지 않는
이유는, 채널 생성처럼 여러 INSERT가 한 트랜잭션으로 묶여야 하는 흐름의
경계를 쿼리 함수가 임의로 끊으면 안 되기 때문이다.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased

from catchup.db.models import ArtifactDefinition
from catchup.db.models import ArtifactOwner
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import ChannelFolder
from catchup.db.models import ChannelPurpose
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import WikiArtifactFavorite

# 문서 목록 한 줄의 상태는 컬럼이 아니라 계류 제안 수와 최신 판에서
# 계산한다. 이름을 상수로 묶어 두어야 서버 계층 필터와 여기 계산이 같은
# 문자열을 쓴다.
ARTIFACT_STATUS_PENDING_REVIEW = "pending_review"
ARTIFACT_STATUS_PUBLISHED = "published"
ARTIFACT_STATUS_NO_REVISION = "no_revision"
ARTIFACT_STATUSES = (
    ARTIFACT_STATUS_PENDING_REVIEW,
    ARTIFACT_STATUS_PUBLISHED,
    ARTIFACT_STATUS_NO_REVISION,
)


def get_user_role(db: Session, user_id: int) -> UserRole | None:
    """사용자의 전역 역할을 읽는다."""
    return db.scalar(select(User.role).where(User.id == user_id))


def list_admin_channel_ids(
    db: Session, *, user_id: int, workspace_id: int
) -> list[uuid.UUID]:
    """이 workspace에서 사용자가 관리자인 채널 id를 읽는다."""
    return list(
        db.scalars(
            select(ChannelAdmin.channel_id)
            .join(Channel, Channel.id == ChannelAdmin.channel_id)
            .where(
                ChannelAdmin.user_id == user_id,
                Channel.workspace_id == workspace_id,
            )
        ).all()
    )


def list_owned_artifact_ids(
    db: Session, *, user_id: int, workspace_id: int
) -> list[uuid.UUID]:
    """이 workspace에서 사용자가 담당자인 문서 id를 읽는다."""
    return list(
        db.scalars(
            select(ArtifactOwner.artifact_id)
            .join(
                KnowledgeArtifact,
                KnowledgeArtifact.id == ArtifactOwner.artifact_id,
            )
            .where(
                ArtifactOwner.user_id == user_id,
                KnowledgeArtifact.workspace_id == workspace_id,
            )
        ).all()
    )


def list_artifact_owner_ids(
    db: Session, artifact_id: uuid.UUID
) -> list[int]:
    """문서의 담당자 사용자 id를 읽는다."""
    return list(
        db.scalars(
            select(ArtifactOwner.user_id).where(
                ArtifactOwner.artifact_id == artifact_id
            )
        ).all()
    )


def get_artifact_channel_id(
    db: Session, artifact_id: uuid.UUID
) -> uuid.UUID | None:
    """문서가 놓인 채널 id를 읽는다.

    문서가 없거나 아직 채널에 놓이지 않았으면 둘 다 None이다.
    """
    return db.scalar(
        select(KnowledgeArtifact.channel_id).where(
            KnowledgeArtifact.id == artifact_id
        )
    )


def get_channel(
    db: Session, *, channel_id: uuid.UUID, workspace_id: int
) -> Channel | None:
    """이 workspace의 채널 하나를 읽는다."""
    return db.scalar(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )


def list_channels(db: Session, workspace_id: int) -> list[Channel]:
    """이 workspace의 채널을 생성순으로 읽는다."""
    return list(
        db.scalars(
            select(Channel)
            .where(Channel.workspace_id == workspace_id)
            .order_by(Channel.created_at, Channel.id)
        ).all()
    )


def add_channel(
    db: Session,
    *,
    workspace_id: int,
    name: str,
    created_by: int,
    style_preset: str | None = None,
) -> Channel:
    """채널 한 개를 세션에 넣는다.

    flush 전이라 id는 아직 비어 있을 수 있다. 채널과 관리자 INSERT를 한
    트랜잭션으로 묶는 쪽이 호출자이므로 flush 시점도 호출자가 정한다.

    preset id는 저장만 한다. 그 값이 카탈로그에 실존하는지는 서버 계층이
    미리 본다 — 쿼리 모듈은 무엇을 넣는지만 안다.
    """
    channel = Channel(
        workspace_id=workspace_id,
        name=name,
        created_by=created_by,
        style_preset=style_preset,
    )
    db.add(channel)

    return channel


def add_artifact_definition(
    db: Session,
    *,
    workspace_id: int,
    channel_id: uuid.UUID,
    kind: str,
    selection_spec: dict[str, Any],
    created_by: int,
    folder_id: uuid.UUID | None = None,
    purpose: str | None = None,
) -> ArtifactDefinition:
    """아티팩트 정의 한 행을 세션에 넣는다.

    selection_spec은 이미 직렬화된 dict을 받는다 — 도메인 dataclass를 db
    모듈이 알 필요가 없다.

    flush·commit은 하지 않는다. 채널·관리자·정의가 한 트랜잭션이어야
    하므로 경계는 호출자가 쥔다.
    """
    definition = ArtifactDefinition(
        workspace_id=workspace_id,
        channel_id=channel_id,
        kind=kind,
        selection_spec=selection_spec,
        created_by=created_by,
        folder_id=folder_id,
        purpose=purpose,
    )
    db.add(definition)

    return definition


def list_definitions_by_channel(
    db: Session, *, channel_id: uuid.UUID
) -> list[ArtifactDefinition]:
    """그 채널에 달린 정의를 kind 사전순으로 읽는다."""
    return list(
        db.scalars(
            select(ArtifactDefinition)
            .where(ArtifactDefinition.channel_id == channel_id)
            .order_by(ArtifactDefinition.kind)
        ).all()
    )


def get_folder(
    db: Session, *, folder_id: uuid.UUID, channel_id: uuid.UUID
) -> ChannelFolder | None:
    """그 채널에 달린 폴더 하나를 읽는다."""
    return db.scalar(
        select(ChannelFolder).where(
            ChannelFolder.id == folder_id,
            ChannelFolder.channel_id == channel_id,
        )
    )


def get_folder_any(db: Session, *, folder_id: uuid.UUID) -> ChannelFolder | None:
    """채널을 가리지 않고 폴더 하나를 읽는다.

    폴더 이동이 실패했을 때 그 폴더가 아예 없는 것인지, 다른 채널에 있는
    것인지를 가르려고 쓴다. 두 경우의 응답 코드가 달라야 소비자가 "없는
    폴더"와 "채널이 다른 폴더"에 서로 다른 화면을 낼 수 있다.
    """
    return db.get(ChannelFolder, folder_id)


def list_folders(db: Session, workspace_id: int) -> list[ChannelFolder]:
    """이 workspace의 폴더를 생성순으로 읽는다."""
    return list(
        db.scalars(
            select(ChannelFolder)
            .where(ChannelFolder.workspace_id == workspace_id)
            .order_by(ChannelFolder.created_at, ChannelFolder.id)
        ).all()
    )


def add_folder(
    db: Session, *, workspace_id: int, channel_id: uuid.UUID, name: str
) -> ChannelFolder:
    """폴더 한 개를 세션에 넣는다."""
    folder = ChannelFolder(
        workspace_id=workspace_id,
        channel_id=channel_id,
        name=name,
    )
    db.add(folder)

    return folder


def remove_folder(db: Session, folder: ChannelFolder) -> None:
    """폴더 한 개를 세션에서 지운다."""
    db.delete(folder)


def get_artifact(
    db: Session, *, artifact_id: uuid.UUID, workspace_id: int
) -> KnowledgeArtifact | None:
    """이 workspace의 문서 한 편을 읽는다."""
    return db.scalar(
        select(KnowledgeArtifact).where(
            KnowledgeArtifact.id == artifact_id,
            KnowledgeArtifact.workspace_id == workspace_id,
        )
    )


def get_latest_revision(
    db: Session, *, artifact_id: uuid.UUID, workspace_id: int
) -> KnowledgeArtifactRevision | None:
    """이 workspace 문서의 가장 최근 발행 판을 읽는다.

    지금 발행된 판은 컬럼이 아니라 판 번호의 최대값이다. 문서는 덮어쓰지
    않고 판을 쌓으므로, 다른 기준을 쓰면 같은 문서를 두 코드가 다르게
    가리킨다.
    """
    return db.scalar(
        select(KnowledgeArtifactRevision)
        .where(
            KnowledgeArtifactRevision.artifact_id == artifact_id,
            KnowledgeArtifactRevision.workspace_id == workspace_id,
        )
        .order_by(KnowledgeArtifactRevision.revision_number.desc())
        .limit(1)
    )


def count_artifacts_by_channel(
    db: Session, workspace_id: int
) -> dict[uuid.UUID, int]:
    """이 workspace의 채널별 문서 수를 읽는다.

    채널에 놓이지 않은 문서는 세지 않는다. 결과에 없는 채널은 0이다.
    """
    return dict(
        db.execute(
            select(
                KnowledgeArtifact.channel_id,
                func.count(KnowledgeArtifact.id),
            )
            .where(
                KnowledgeArtifact.workspace_id == workspace_id,
                KnowledgeArtifact.channel_id.is_not(None),
            )
            .group_by(KnowledgeArtifact.channel_id)
        ).all()
    )


def list_channel_admin_ids(
    db: Session, channel_id: uuid.UUID
) -> list[int]:
    """채널 관리자의 사용자 id를 읽는다."""
    return list(
        db.scalars(
            select(ChannelAdmin.user_id).where(
                ChannelAdmin.channel_id == channel_id
            )
        ).all()
    )


def get_channel_admin(
    db: Session, *, channel_id: uuid.UUID, user_id: int
) -> ChannelAdmin | None:
    """채널 관리자 행 하나를 읽는다."""
    return db.get(ChannelAdmin, (channel_id, user_id))


def add_channel_admin(
    db: Session, *, channel_id: uuid.UUID, user_id: int, granted_by: int
) -> ChannelAdmin:
    """채널 관리자 행 하나를 세션에 넣는다."""
    admin = ChannelAdmin(
        channel_id=channel_id,
        user_id=user_id,
        granted_by=granted_by,
    )
    db.add(admin)

    return admin


def get_artifact_owner(
    db: Session, *, artifact_id: uuid.UUID, user_id: int
) -> ArtifactOwner | None:
    """문서 담당자 행 하나를 읽는다."""
    return db.get(ArtifactOwner, (artifact_id, user_id))


def add_artifact_owner(
    db: Session, *, artifact_id: uuid.UUID, user_id: int, granted_by: int
) -> ArtifactOwner:
    """문서 담당자 행 하나를 세션에 넣는다."""
    owner = ArtifactOwner(
        artifact_id=artifact_id,
        user_id=user_id,
        granted_by=granted_by,
    )
    db.add(owner)

    return owner


def remove_artifact_owner(db: Session, owner: ArtifactOwner) -> None:
    """문서 담당자 행 하나를 세션에서 지운다."""
    db.delete(owner)


def get_workspace_membership_user_id(
    db: Session, *, user_id: int, workspace_id: int
) -> int | None:
    """이 사용자가 그 workspace 구성원인지를 행 존재로 읽는다."""
    return db.scalar(
        select(UserWorkspace.user_id).where(
            UserWorkspace.user_id == user_id,
            UserWorkspace.workspace_id == workspace_id,
        )
    )


def list_membership_workspace_ids(db: Session, user_id: int) -> list[int]:
    """사용자가 속한 workspace id를 오름차순으로 읽는다."""
    return list(
        db.scalars(
            select(UserWorkspace.workspace_id)
            .where(UserWorkspace.user_id == user_id)
            .order_by(UserWorkspace.workspace_id)
        ).all()
    )


# ======================= 담당자·위치 =======================


@dataclass(frozen=True, slots=True)
class OwnerRow:
    """담당자 한 명을 화면에 그릴 만큼만 담는다."""

    artifact_id: uuid.UUID
    user_id: int
    display_name: str
    profile_image_url: str | None


def list_owners_by_artifact(
    db: Session, *, artifact_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[OwnerRow]]:
    """여러 문서의 담당자를 사용자 이름·사진과 함께 문서별로 묶어 읽는다.

    문서 하나씩 조회하면 목록 한 쪽에 질의가 행 수만큼 늘어난다. 그래서
    id 목록을 한 번에 받아 in으로 읽고 dict으로 나눈다. 담당자가 없는
    문서는 결과에 키가 없다.
    """
    if not artifact_ids:
        return {}

    rows = db.execute(
        select(
            ArtifactOwner.artifact_id,
            ArtifactOwner.user_id,
            User.name,
            User.picture,
        )
        .join(User, User.id == ArtifactOwner.user_id)
        .where(ArtifactOwner.artifact_id.in_(artifact_ids))
        .order_by(ArtifactOwner.artifact_id, ArtifactOwner.user_id)
    ).all()

    grouped: dict[uuid.UUID, list[OwnerRow]] = defaultdict(list)
    for artifact_id, user_id, name, picture in rows:
        grouped[artifact_id].append(OwnerRow(artifact_id, user_id, name, picture))

    return dict(grouped)


@dataclass(frozen=True, slots=True)
class WorkspaceMemberRow:
    """워크스페이스 구성원 한 명을 화면에 그릴 만큼만 담는다.

    OwnerRow와 필드가 같지만 따로 둔다. 그쪽은 artifact_id를 함께 갖는
    "어느 문서의 담당자"라, 아직 어느 문서에도 붙지 않은 구성원에는 채울
    값이 없다.
    """

    user_id: int
    display_name: str
    profile_image_url: str | None


def list_workspace_members(
    db: Session, *, workspace_id: int
) -> list[WorkspaceMemberRow]:
    """이 workspace의 활성 구성원을 이름 순으로 읽는다.

    비활성·삭제된 사용자는 뺀다. 담당자로 지정할 사람을 고르는 자리에서
    쓰이므로, 이미 떠난 사람이 후보로 보이면 안 된다.

    이름이 같은 사람이 있을 수 있어 id로 한 번 더 세운다. 순서가 흔들리면
    같은 목록을 두 번 열었을 때 항목이 자리를 바꾼다.
    """
    rows = db.execute(
        select(User.id, User.name, User.picture)
        .join(UserWorkspace, UserWorkspace.user_id == User.id)
        .where(
            UserWorkspace.workspace_id == workspace_id,
            User.status == UserStatus.ACTIVE,
        )
        .order_by(User.name, User.id)
    ).all()

    return [
        WorkspaceMemberRow(user_id, name, picture)
        for user_id, name, picture in rows
    ]


def get_artifact_locations(
    db: Session, *, artifact_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID | None, uuid.UUID | None]]:
    """여러 문서가 놓인 (채널, 폴더)를 한 번에 읽는다.

    미분류 문서는 둘 다 None이고, 채널 루트에 있는 문서는 폴더만 None이다.
    없는 id는 결과에 키가 없다.
    """
    if not artifact_ids:
        return {}

    rows = db.execute(
        select(
            KnowledgeArtifact.id,
            KnowledgeArtifact.channel_id,
            KnowledgeArtifact.folder_id,
        ).where(KnowledgeArtifact.id.in_(artifact_ids))
    ).all()

    return {
        artifact_id: (channel_id, folder_id)
        for artifact_id, channel_id, folder_id in rows
    }


def list_artifact_ids_by_channel(
    db: Session, *, workspace_id: int, channel_id: uuid.UUID
) -> list[uuid.UUID]:
    """그 채널에 놓인 문서 id를 읽는다."""
    return list(
        db.scalars(
            select(KnowledgeArtifact.id).where(
                KnowledgeArtifact.workspace_id == workspace_id,
                KnowledgeArtifact.channel_id == channel_id,
            )
        ).all()
    )


def list_artifact_ids_by_owner(
    db: Session, *, workspace_id: int, user_id: int
) -> list[uuid.UUID]:
    """이 workspace에서 그 사용자가 담당자인 문서 id를 읽는다."""
    return list(
        db.scalars(
            select(ArtifactOwner.artifact_id)
            .join(
                KnowledgeArtifact,
                KnowledgeArtifact.id == ArtifactOwner.artifact_id,
            )
            .where(
                ArtifactOwner.user_id == user_id,
                KnowledgeArtifact.workspace_id == workspace_id,
            )
        ).all()
    )


def set_artifact_folder(
    db: Session, *, artifact: KnowledgeArtifact, folder_id: uuid.UUID | None
) -> None:
    """문서를 채널 안의 다른 폴더로 옮긴다. None이면 채널 루트로 올린다.

    폴더가 그 문서의 채널에 달린 것인지는 서버 계층이 미리 본다.
    """
    artifact.folder_id = folder_id


# ======================= 채널 목적 =======================


def list_channel_purposes(db: Session, *, channel_id: uuid.UUID) -> list[str]:
    """채널이 고른 목적 preset id를 고른 순서대로 읽는다."""
    return list(
        db.scalars(
            select(ChannelPurpose.purpose_preset)
            .where(ChannelPurpose.channel_id == channel_id)
            .order_by(ChannelPurpose.position)
        ).all()
    )


def add_channel_purposes(
    db: Session, *, channel_id: uuid.UUID, purpose_presets: Sequence[str]
) -> None:
    """채널 목적 여러 개를 받은 순서 그대로 세션에 넣는다.

    position은 받은 순서다. 사용자가 고른 차례가 곧 노출 차례라서, 순서를
    따로 저장하지 않으면 다시 읽을 때 되살릴 수 없다.
    """
    for position, preset in enumerate(purpose_presets):
        db.add(
            ChannelPurpose(
                channel_id=channel_id,
                purpose_preset=preset,
                position=position,
            )
        )


def list_channel_purposes_by_workspace(
    db: Session, workspace_id: int
) -> dict[uuid.UUID, list[str]]:
    """이 workspace 채널들의 목적을 채널별로 묶어 읽는다.

    채널 목록 화면이 채널마다 따로 묻지 않게 한 번에 읽는다. 목적이 없는
    채널은 결과에 키가 없다.
    """
    rows = db.execute(
        select(ChannelPurpose.channel_id, ChannelPurpose.purpose_preset)
        .join(Channel, Channel.id == ChannelPurpose.channel_id)
        .where(Channel.workspace_id == workspace_id)
        .order_by(ChannelPurpose.channel_id, ChannelPurpose.position)
    ).all()

    grouped: dict[uuid.UUID, list[str]] = defaultdict(list)
    for channel_id, preset in rows:
        grouped[channel_id].append(preset)

    return dict(grouped)


# ======================= 폴더·정의 =======================


def get_folder_by_name(
    db: Session, *, channel_id: uuid.UUID, name: str
) -> ChannelFolder | None:
    """그 채널 안에서 이름이 같은 폴더를 읽는다.

    (channel_id, name)이 UNIQUE라 있으면 하나다. 온보딩이 같은 이름 폴더를
    두 번 만들지 않으려고 먼저 본다.
    """
    return db.scalar(
        select(ChannelFolder).where(
            ChannelFolder.channel_id == channel_id,
            ChannelFolder.name == name,
        )
    )


def list_definitions_by_workspace(
    db: Session, workspace_id: int
) -> dict[uuid.UUID, list[ArtifactDefinition]]:
    """이 workspace의 정의를 채널별로 묶어 kind 사전순으로 읽는다.

    정의가 없는 채널은 결과에 키가 없다.
    """
    rows = db.scalars(
        select(ArtifactDefinition)
        .where(ArtifactDefinition.workspace_id == workspace_id)
        .order_by(ArtifactDefinition.channel_id, ArtifactDefinition.kind)
    ).all()

    grouped: dict[uuid.UUID, list[ArtifactDefinition]] = defaultdict(list)
    for definition in rows:
        grouped[definition.channel_id].append(definition)

    return dict(grouped)


# ======================= 문서 목록 =======================


def _escape_like(text: str) -> str:
    """LIKE 패턴에서 특별한 뜻을 갖는 글자를 글자 그대로 찾도록 바꾼다.

    사용자가 친 검색어에 %나 _가 들어 있으면 LIKE는 그것을 "아무 글자"로
    읽는다. 제목에 실제로 들어 있는 %를 찾으려는 사람에게 엉뚱한 문서가
    걸리므로, 앞에 \\를 붙여 글자로 되돌린다. \\ 자체도 먼저 바꾼다.
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True, slots=True)
class ArtifactListRow:
    """문서 목록 한 줄이다. 상태는 컬럼이 아니라 아래 두 값에서 계산한다."""

    artifact_id: uuid.UUID
    kind: str
    title: str
    channel_id: uuid.UUID | None
    folder_id: uuid.UUID | None
    created_at: datetime
    pending_proposal_count: int
    latest_revision_id: uuid.UUID | None
    latest_revision_number: int | None
    latest_published_at: datetime | None
    # 마지막 활동 시각이다. 발행과 제안 도착 중 늦은 쪽이고, 둘 다 없으면
    # 문서 생성 시각이다. 항상 값이 있다.
    last_activity_at: datetime


def artifact_status(row: ArtifactListRow) -> str:
    """문서 목록 한 줄의 상태를 계산한다. 계류 제안이 있으면 검토 대기가 우선이다."""
    if row.pending_proposal_count > 0:
        return ARTIFACT_STATUS_PENDING_REVIEW
    if row.latest_revision_id is not None:
        return ARTIFACT_STATUS_PUBLISHED
    return ARTIFACT_STATUS_NO_REVISION


def list_artifacts(
    db: Session,
    *,
    workspace_id: int,
    channel_id: uuid.UUID | None = None,
    folder_id: uuid.UUID | None = None,
    kind: str | None = None,
    status: str | None = None,
    owner_user_id: int | None = None,
    unassigned: bool = False,
    q: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: str = "last_activity",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ArtifactListRow], int]:
    """문서 목록 한 쪽과 필터 뒤 전체 수를 돌려준다.

    계류 제안 수와 최신 판은 상관 서브쿼리로 붙인다. 상태 필터는 그 두 값
    위에서 계산한 CASE 식에 건다.

    정렬 키는 last_activity(마지막 활동 시각)와 created_at 둘 중 하나이고
    방향은 asc·desc다. 값이 같은 문서끼리는 언제나 id 오름차순으로 세운다.
    동률 순서를 고정하지 않으면 같은 조건으로 다음 쪽을 요청했을 때 앞
    쪽에서 이미 본 문서가 다시 나오거나 아예 빠질 수 있다.

    owner_user_id와 unassigned를 함께 받으면 결과가 반드시 비지만, 여기서는
    막지 않고 받은 대로 건다. 잘못된 조합을 거르는 일은 서버 계층의 몫이다.
    """
    pending_count = (
        select(func.count(KnowledgeArtifactChangeProposal.id))
        .where(
            KnowledgeArtifactChangeProposal.artifact_id == KnowledgeArtifact.id,
            KnowledgeArtifactChangeProposal.status == "pending",
        )
        .correlate(KnowledgeArtifact)
        .scalar_subquery()
    )
    latest = (
        select(
            KnowledgeArtifactRevision.artifact_id.label("artifact_id"),
            func.max(KnowledgeArtifactRevision.revision_number).label(
                "revision_number"
            ),
        )
        .where(KnowledgeArtifactRevision.workspace_id == workspace_id)
        .group_by(KnowledgeArtifactRevision.artifact_id)
        .subquery()
    )
    latest_row = aliased(KnowledgeArtifactRevision)
    latest_proposal_at = (
        select(func.max(KnowledgeArtifactChangeProposal.created_at))
        .where(
            KnowledgeArtifactChangeProposal.artifact_id == KnowledgeArtifact.id
        )
        .correlate(KnowledgeArtifact)
        .scalar_subquery()
    )
    # 제안은 status를 가리지 않고 센다. 반려된 제안이라도 도착했다는 것
    # 자체가 문서가 움직인 사실이고, 화면은 그 움직임을 보여 준다.
    last_activity_expr = func.greatest(
        func.coalesce(latest_row.created_at, KnowledgeArtifact.created_at),
        func.coalesce(latest_proposal_at, KnowledgeArtifact.created_at),
    )
    status_expr = case(
        (pending_count > 0, ARTIFACT_STATUS_PENDING_REVIEW),
        (latest_row.id.is_not(None), ARTIFACT_STATUS_PUBLISHED),
        else_=ARTIFACT_STATUS_NO_REVISION,
    )
    statement = (
        select(
            KnowledgeArtifact.id,
            KnowledgeArtifact.kind,
            KnowledgeArtifact.title,
            KnowledgeArtifact.channel_id,
            KnowledgeArtifact.folder_id,
            KnowledgeArtifact.created_at,
            pending_count.label("pending_proposal_count"),
            latest_row.id.label("latest_revision_id"),
            latest_row.revision_number.label("latest_revision_number"),
            latest_row.created_at.label("latest_published_at"),
            last_activity_expr.label("last_activity_at"),
        )
        .outerjoin(latest, latest.c.artifact_id == KnowledgeArtifact.id)
        .outerjoin(
            latest_row,
            (latest_row.artifact_id == KnowledgeArtifact.id)
            & (latest_row.revision_number == latest.c.revision_number),
        )
        .where(KnowledgeArtifact.workspace_id == workspace_id)
    )
    if channel_id is not None:
        statement = statement.where(KnowledgeArtifact.channel_id == channel_id)
    if folder_id is not None:
        statement = statement.where(KnowledgeArtifact.folder_id == folder_id)
    if kind is not None:
        statement = statement.where(KnowledgeArtifact.kind == kind)
    if status is not None:
        statement = statement.where(status_expr == status)
    if owner_user_id is not None:
        statement = statement.where(
            KnowledgeArtifact.id.in_(
                select(ArtifactOwner.artifact_id).where(
                    ArtifactOwner.user_id == owner_user_id
                )
            )
        )
    if unassigned:
        statement = statement.where(
            ~select(ArtifactOwner.artifact_id)
            .where(ArtifactOwner.artifact_id == KnowledgeArtifact.id)
            .correlate(KnowledgeArtifact)
            .exists()
        )
    if q is not None and q.strip():
        statement = statement.where(
            KnowledgeArtifact.title.ilike(
                f"%{_escape_like(q.strip())}%", escape="\\"
            )
        )
    if created_after is not None:
        statement = statement.where(KnowledgeArtifact.created_at >= created_after)
    if created_before is not None:
        statement = statement.where(KnowledgeArtifact.created_at <= created_before)

    sort_expr = (
        KnowledgeArtifact.created_at
        if sort == "created_at"
        else last_activity_expr
    )
    ordered = sort_expr.asc() if order == "asc" else sort_expr.desc()

    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = db.execute(
        statement.order_by(ordered, KnowledgeArtifact.id)
        .limit(limit)
        .offset(offset)
    ).all()

    return [ArtifactListRow(*row) for row in rows], int(total or 0)


# ======================= 즐겨찾기 =======================


def is_favorite(db: Session, *, user_id: int, artifact_id: uuid.UUID) -> bool:
    """그 사용자가 이 문서를 즐겨찾기했는지 행 존재로 읽는다."""
    return (db.get(WikiArtifactFavorite, (user_id, artifact_id))) is not None


def list_favorite_artifact_ids(
    db: Session, *, user_id: int, workspace_id: int
) -> set[uuid.UUID]:
    """이 workspace에서 그 사용자가 즐겨찾기한 문서 id를 읽는다.

    목록 화면이 줄마다 즐겨찾기 여부를 표시할 때 한 번에 읽어 쓴다.
    """
    return set(
        db.scalars(
            select(WikiArtifactFavorite.artifact_id).where(
                WikiArtifactFavorite.user_id == user_id,
                WikiArtifactFavorite.workspace_id == workspace_id,
            )
        ).all()
    )


def list_favorites(
    db: Session, *, user_id: int, workspace_id: int
) -> list[tuple[KnowledgeArtifact, datetime]]:
    """즐겨찾기한 문서를 최근에 담은 순으로 읽는다."""
    rows = db.execute(
        select(KnowledgeArtifact, WikiArtifactFavorite.created_at)
        .join(
            WikiArtifactFavorite,
            WikiArtifactFavorite.artifact_id == KnowledgeArtifact.id,
        )
        .where(
            WikiArtifactFavorite.user_id == user_id,
            WikiArtifactFavorite.workspace_id == workspace_id,
        )
        .order_by(WikiArtifactFavorite.created_at.desc(), KnowledgeArtifact.id)
    ).all()

    return [(artifact, favorited_at) for artifact, favorited_at in rows]


def add_favorite(
    db: Session, *, user_id: int, artifact_id: uuid.UUID, workspace_id: int
) -> bool:
    """즐겨찾기 행 하나를 세션에 넣는다. 새로 넣었으면 True다.

    같은 요청을 두 번 보내도 오류가 아니라 False다. 즐겨찾기는 있고 없고만
    의미가 있어, 이미 있는 상태를 실패로 볼 이유가 없다.
    """
    if db.get(WikiArtifactFavorite, (user_id, artifact_id)) is not None:
        return False

    db.add(
        WikiArtifactFavorite(
            user_id=user_id,
            artifact_id=artifact_id,
            workspace_id=workspace_id,
        )
    )

    return True


def remove_favorite(db: Session, *, user_id: int, artifact_id: uuid.UUID) -> bool:
    """즐겨찾기 행 하나를 세션에서 지운다. 지울 것이 있었으면 True다."""
    favorite = db.get(WikiArtifactFavorite, (user_id, artifact_id))
    if favorite is None:
        return False

    db.delete(favorite)

    return True
