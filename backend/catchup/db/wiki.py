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
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import ArtifactDefinition
from catchup.db.models import ArtifactOwner
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import ChannelFolder
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserWorkspace


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
    purpose_preset: str | None = None,
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
        purpose_preset=purpose_preset,
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
