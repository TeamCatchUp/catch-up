"""검수 루프 정식 API의 인가·응답·오류 계약을 확인한다.

권한 판정은 실 PostgreSQL로 본다. 소속(user_workspaces)과 위키 역할
(channel_admins·artifact_owners·users.role)이 모두 DB 사실이고, 대역으로
흉내내면 조인 조건이 틀려도 드러나지 않기 때문이다. 인증만
dependency_overrides로 우회한다 — 쿠키 JWT를 만드는 일은 이 라우터의 검증
대상이 아니다.

인가는 두 겹이라 확인도 두 겹이다. 의존성이 보는 "이 표면에 설 자격"은
NOT_REVIEWER로, 핸들러가 보는 "이 문서를 결정할 자격"은
NOT_DOCUMENT_REVIEWER로 갈린다. 다만 첫 겹은 경로에 따라 다르다. 큐 목록과
상세는 workspace 구성원이면 열리므로 역할 없는 사람에게 NOT_MEMBER만 걸리고,
판정 경로에서만 NOT_REVIEWER가 걸린다. 대부분의 응답 계약 테스트는 전역 ADMIN을
검토자로 세운다 — 대역 변경안이 가리키는 문서는 DB에 없어 미분류로 읽히고,
미분류의 폴백이 전역 ADMIN이기 때문이다.

반면 결정 서비스는 대역으로 바꾼다. 불변식은 서비스 쪽 테스트가 이미
지키고, 여기서 볼 것은 라우터가 무엇을 넘기고 예외를 어떤 코드로 옮기는지
뿐이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone
from types import TracebackType
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db.models import ArtifactDefinition
from catchup.db.models import ArtifactOwner
from catchup.db.models import Channel
from catchup.db.models import ChannelAdmin
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal
from catchup.db.models import KnowledgeArtifactRevision
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.services.list_review_queue import ReviewQueueItem
from catchup.knowledge_maintenance.services.list_review_queue import ReviewQueuePage
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    PublishError,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    PublishResult,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import ReviewResult
from catchup.server.knowledge_review.api import _to_base_block
from catchup.server.knowledge_review.api import _to_block
from catchup.server.knowledge_review.api import router
from catchup.server.knowledge_review.dependencies import ReviewerContext
from catchup.server.knowledge_review.dependencies import get_member_review_uow_factory
from catchup.server.knowledge_review.dependencies import get_review_uow_factory
from catchup.server.knowledge_review.dependencies import get_reviewer_user
from catchup.server.knowledge_review.dependencies import resolve_reviewer_workspace
from catchup.server.wiki.roles import WikiRoleContext

AT = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


# ======================= 실 DB fixture =======================


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ChannelAdmin.__tablename__):
        engine.dispose()
        pytest.skip("역할 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def workspace_ids(engine: Engine) -> tuple[int, int]:
    """실 DB에 있는 workspace 두 개를 빌린다.

    workspace를 새로 만들려면 company까지 함께 만들어야 하고, 그것은 이
    테스트가 검증하려는 것과 무관한 사전 준비다.
    """
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.id).order_by(Workspace.id).limit(2)
        ).scalars().all()

    if len(found) < 2:
        pytest.skip("workspace가 둘 이상 없어 통합 테스트를 건너뛴다.")
    return found[0], found[1]


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """테스트마다 되감는 연결 하나를 만든다.

    바깥 트랜잭션을 롤백하므로 여기서 만든 사용자·권한·문서 행은 남지
    않는다.
    """
    connection = engine.connect()
    transaction = connection.begin()

    yield connection

    transaction.rollback()
    connection.close()


@pytest.fixture
def session_factory(connection: Connection) -> Callable[[], Session]:
    """같은 트랜잭션 위에 세션을 여는 factory를 만든다.

    실 UnitOfWork에 물릴 수 있어야 한다. 별도 연결을 쓰면 커밋하지 않은
    테스트 데이터가 UoW 쪽에서 보이지 않아, 저장소 질의를 실 DB로 확인할
    방법이 없어진다.
    """
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
def db(session_factory: Callable[[], Session]) -> Iterator[Session]:
    """권한 행을 넣고 읽을 세션을 만든다."""
    session = session_factory()

    yield session

    session.close()


def _make_user(db: Session, *, email: str) -> User:
    """테스트용 사용자 한 명을 만든다."""
    user = User(
        email=email,
        name="검토자",
        provider="keycloak",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    return user


def _join(db: Session, *, user: User, workspace_id: int) -> None:
    """사용자를 workspace 구성원으로 넣는다."""
    db.add(UserWorkspace(user_id=user.id, workspace_id=workspace_id))
    db.flush()


def _grant(db: Session, *, user: User, workspace_id: int) -> None:
    """검수 표면에 설 자격을 준다.

    전역 ADMIN으로 세우는 이유는 대역 변경안이 가리키는 문서가 DB에 없어
    미분류로 읽히기 때문이다. 미분류의 폴백이 전역 ADMIN이라, 응답 계약을
    보는 테스트들이 대상 판정에 걸리지 않고 본론에 닿는다. workspace_id는
    호출부의 뜻(이 workspace에서 검수한다)을 남기려고 받는다 — 전역 역할은
    workspace로 갈리지 않는다.
    """
    del workspace_id
    user.role = UserRole.ADMIN
    db.flush()


def _make_channel(db: Session, *, workspace_id: int, created_by: int) -> uuid.UUID:
    """채널 하나를 만든다."""
    channel_id = uuid.uuid4()
    db.add(
        Channel(
            id=channel_id,
            workspace_id=workspace_id,
            name=f"채널-{uuid.uuid4().hex[:8]}",
            created_by=created_by,
        )
    )
    db.flush()
    return channel_id


def _make_channel_admin(
    db: Session, *, channel_id: uuid.UUID, user: User
) -> None:
    """사용자를 채널 관리자로 세운다."""
    db.add(ChannelAdmin(channel_id=channel_id, user_id=user.id))
    db.flush()


def _make_artifact(
    db: Session, *, workspace_id: int, channel_id: uuid.UUID | None = None
) -> uuid.UUID:
    """주제 노드까지 갖춘 문서 한 편을 만든다."""
    node_id = uuid.uuid4()
    db.add(
        KnowledgeNode(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="feature",
            canonical_key=f"test:roles:{uuid.uuid4().hex}",
            display_name="속도 제한 기능",
        )
    )
    db.flush()
    artifact_id = uuid.uuid4()
    db.add(
        KnowledgeArtifact(
            id=artifact_id,
            workspace_id=workspace_id,
            kind="entity_summary",
            channel_id=channel_id,
            subject_node_id=node_id,
            title="오픈 API",
        )
    )
    db.flush()
    return artifact_id


def _make_owner(db: Session, *, artifact_id: uuid.UUID, user: User) -> None:
    """사용자를 그 문서의 담당자로 세운다."""
    db.add(ArtifactOwner(artifact_id=artifact_id, user_id=user.id))
    db.flush()


def _roles(**kwargs) -> WikiRoleContext:
    """컨텍스트를 직접 만들 때 쓸 역할 스냅샷을 만든다."""
    base = dict(
        is_global_admin=False,
        admin_channel_ids=frozenset(),
        owned_artifact_ids=frozenset(),
    )
    base.update(kwargs)
    return WikiRoleContext(**base)


# ======================= 대역 UnitOfWork =======================


class _FakeArtifacts:
    """검토 큐·상세가 읽는 artifact 저장소를 흉내낸다."""

    def __init__(
        self,
        *,
        proposal: StoredArtifactProposal | None = None,
        latest: tuple[uuid.UUID, int] | None = None,
    ) -> None:
        self._proposal = proposal
        self._latest = latest

    def get_proposal(
        self, *, proposal_id: uuid.UUID, for_update: bool = False
    ) -> StoredArtifactProposal | None:
        if self._proposal is None or self._proposal.id != proposal_id:
            return None
        return self._proposal

    def find_latest_revision_id_and_number(
        self, *, artifact_id: uuid.UUID
    ) -> tuple[uuid.UUID, int] | None:
        return self._latest


class _FakeMutations:
    """모순 안건 조회만 흉내낸다."""

    def __init__(
        self,
        *,
        pending: tuple[StoredContradictionProposal, ...] = (),
        subject_pending: tuple[StoredPendingProposal, ...] = (),
        statuses: dict[uuid.UUID, str] | None = None,
    ) -> None:
        self._pending = pending
        self._subject_pending = subject_pending
        # 실 저장소처럼 계류 여부와 무관하게 상태를 돌려준다. 계류 목록에
        # 없는 안건도 행 자체는 남아 있기 때문이다.
        self._statuses = dict(statuses or {})
        self.workspace_ids: list[int] = []

    def find_pending_for_subject_node(
        self, *, workspace_id: int, node_id: uuid.UUID
    ) -> list[StoredPendingProposal]:
        self.workspace_ids.append(workspace_id)
        return list(self._subject_pending)

    def list_pending_contradictions(
        self, *, workspace_id: int
    ) -> list[StoredContradictionProposal]:
        self.workspace_ids.append(workspace_id)
        return list(self._pending)

    def get_contradiction_status(
        self, *, workspace_id: int, proposal_id: uuid.UUID
    ) -> str | None:
        self.workspace_ids.append(workspace_id)
        return self._statuses.get(proposal_id)


class _FakeBlockVerdicts:
    """블록 결정 저널 조회만 흉내낸다."""

    def __init__(
        self, *, stored: tuple[StoredBlockVerdict, ...] = ()
    ) -> None:
        self._stored = stored

    def list_for_proposal(
        self, *, proposal_id: uuid.UUID
    ) -> tuple[StoredBlockVerdict, ...]:
        return tuple(
            item for item in self._stored if item.proposal_id == proposal_id
        )


class _FakeUow:
    """라우터가 쓰는 transaction 경계를 흉내낸다."""

    def __init__(
        self,
        *,
        artifacts: _FakeArtifacts,
        mutation_proposals: _FakeMutations,
        block_verdicts: _FakeBlockVerdicts,
    ) -> None:
        self.artifacts = artifacts
        self.mutation_proposals = mutation_proposals
        self.block_verdicts = block_verdicts

    def __enter__(self) -> _FakeUow:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        return None


def _fake_factory(
    *,
    artifacts: _FakeArtifacts | None = None,
    mutations: _FakeMutations | None = None,
    verdicts: _FakeBlockVerdicts | None = None,
) -> Callable[[], _FakeUow]:
    """같은 대역 저장소를 계속 돌려주는 factory를 만든다."""
    resolved_artifacts = artifacts or _FakeArtifacts()
    resolved_mutations = mutations or _FakeMutations()
    resolved_verdicts = verdicts or _FakeBlockVerdicts()

    def factory() -> _FakeUow:
        return _FakeUow(
            artifacts=resolved_artifacts,
            mutation_proposals=resolved_mutations,
            block_verdicts=resolved_verdicts,
        )

    return factory


def _proposal(
    *,
    proposal_id: uuid.UUID,
    status: str = "pending",
    subject_node_id: uuid.UUID | None = None,
    base_revision_id: uuid.UUID | None = None,
    claim_id: uuid.UUID | None = None,
    artifact_id: uuid.UUID | None = None,
    sources: tuple[BlockSource, ...] = (),
) -> StoredArtifactProposal:
    """상세 응답에 쓸 변경안 한 건을 만든다.

    sources를 주는 호출자는 claim_id도 같이 줘서 근거 인용이 블록
    claim_ids 안에 들게 한다 — 도메인 검증이 요구하는 부분집합 관계를
    대역에서도 지킨다.
    """
    return StoredArtifactProposal(
        id=proposal_id,
        artifact_id=artifact_id or uuid.uuid4(),
        subject_node_id=subject_node_id or uuid.uuid4(),
        title="오픈 API",
        status=status,
        blocks=(
            ArtifactBlock(
                block_kind="claim_section",
                heading="속도 제한",
                body="rate_limit은 60이다",
                claim_ids=(claim_id or uuid.uuid4(),),
                proposal_ids=(),
                ontology_version="v1",
                sources=sources,
            ),
        ),
        content_hash="hash",
        base_revision_id=base_revision_id,
        rejection_reason=None,
        origin="compiled",
        created_at=AT,
    )


def _contested_proposal(
    *,
    proposal_id: uuid.UUID,
    contradiction_id: uuid.UUID,
    winner_claim_id: uuid.UUID,
    loser_claim_id: uuid.UUID,
    subject_node_id: uuid.UUID | None = None,
) -> StoredArtifactProposal:
    """다툼 블록 하나만 가진 변경안을 만든다."""
    return StoredArtifactProposal(
        id=proposal_id,
        artifact_id=uuid.uuid4(),
        subject_node_id=subject_node_id or uuid.uuid4(),
        title="오픈 API",
        status="pending",
        blocks=(
            ArtifactBlock(
                block_kind=BLOCK_KIND_CONTESTED,
                heading="속도 제한",
                body="값이 갈렸다",
                claim_ids=(winner_claim_id, loser_claim_id),
                proposal_ids=(contradiction_id,),
                ontology_version="v1",
                sources=(),
                variants=(
                    ContestedVariant(
                        claim_id=winner_claim_id,
                        body="rate_limit은 60이다",
                        sources=(
                            BlockSource(
                                claim_id=winner_claim_id,
                                statement="rate_limit은 60이다",
                                observed_at=AT,
                                citation_verified=True,
                            ),
                        ),
                    ),
                    ContestedVariant(
                        claim_id=loser_claim_id,
                        body="rate_limit은 120이다",
                        sources=(),
                    ),
                ),
            ),
        ),
        content_hash="hash",
        base_revision_id=None,
        rejection_reason=None,
        origin="compiled",
        created_at=AT,
    )


def _relation_proposal(
    *,
    proposal_id: uuid.UUID,
    relation_id: uuid.UUID,
) -> StoredArtifactProposal:
    """relation_section 블록 하나만 가진 변경안을 만든다.

    relation_section의 근거 장부는 relation_ids 하나뿐이라 claim_ids는
    비운다 — 도메인 계약이 둘을 함께 채우는 것을 막는다.
    """
    return StoredArtifactProposal(
        id=proposal_id,
        artifact_id=uuid.uuid4(),
        subject_node_id=uuid.uuid4(),
        title="오픈 API",
        status="pending",
        blocks=(
            ArtifactBlock(
                block_kind=BLOCK_KIND_RELATION_SECTION,
                heading="의존 관계",
                body="오픈 API는 인증 서비스에 의존한다",
                claim_ids=(),
                proposal_ids=(),
                ontology_version="v1",
                relation_ids=(relation_id,),
            ),
        ),
        content_hash="hash",
        base_revision_id=None,
        rejection_reason=None,
        origin="compiled",
        created_at=AT,
    )


# ======================= 앱 fixture =======================


class _UowOverrides(dict):
    """UoW factory 우회를 열람 경로에도 같이 걸어 주는 override 사전이다.

    라우터의 UoW factory 의존성은 두 개다. 판정 경로는
    `get_review_uow_factory`를, 목록·상세 열람 경로는
    `get_member_review_uow_factory`를 쓴다. 테스트는 어느 라우트를 부르든
    같은 대역 저장소를 보길 원하므로, 한쪽을 덮으면 다른 쪽도 같은 값으로
    덮는다. 테스트마다 두 줄을 쓰게 두면 한쪽만 덮은 테스트가 실 DB로
    새어 나가 원인을 찾기 어려운 실패가 된다.
    """

    def __setitem__(self, key: object, value: object) -> None:
        super().__setitem__(key, value)
        if key is get_review_uow_factory:
            super().__setitem__(get_member_review_uow_factory, value)
        elif key is get_member_review_uow_factory:
            super().__setitem__(get_review_uow_factory, value)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides = _UowOverrides()
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def as_user(app: FastAPI, db: Session) -> Callable[[User], None]:
    """인증만 우회한다. 소속·권한 검사는 실 DB로 그대로 돈다.

    우회하는 자리는 라우터가 실제로 의존하는 `get_reviewer_user`다. 그
    아래의 `get_current_user`를 덮으면 래핑을 지나지 않아, 401 계약이
    깨져도 테스트가 알아채지 못한다.
    """

    def register(user: User) -> None:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_reviewer_user] = lambda: user

    return register


# ======================= 의존성: workspace 확정 =======================


def test_single_workspace_user_resolves_implicitly(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """소속이 하나면 workspace를 주지 않아도 그것으로 정해진다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="one@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    _grant(db, user=user, workspace_id=workspace_id)

    context = resolve_reviewer_workspace(current_user=user, db=db)

    assert context.workspace_id == workspace_id
    assert context.user is user


def test_multi_workspace_user_requires_explicit_param(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """여러 곳에 속하면 workspace 명시를 요구한다."""
    first, second = workspace_ids
    user = _make_user(db, email="many@example.com")
    _join(db, user=user, workspace_id=first)
    _join(db, user=user, workspace_id=second)
    _grant(db, user=user, workspace_id=first)

    with pytest.raises(HTTPException) as excinfo:
        resolve_reviewer_workspace(current_user=user, db=db)

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["code"] == "WORKSPACE_REQUIRED"


def test_member_without_roles_is_403(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """소속만 있고 아무 역할도 없으면 막는다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="member@example.com")
    _join(db, user=user, workspace_id=workspace_id)

    with pytest.raises(HTTPException) as excinfo:
        resolve_reviewer_workspace(
            workspace_id=workspace_id, current_user=user, db=db
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "NOT_REVIEWER"


def test_channel_admin_role_opens_the_surface(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """이 workspace의 채널 관리자면 검수 표면에 설 수 있다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="channel-admin@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=user.id
    )
    _make_channel_admin(db, channel_id=channel_id, user=user)

    context = resolve_reviewer_workspace(
        workspace_id=workspace_id, current_user=user, db=db
    )

    assert context.roles.admin_channel_ids == frozenset({channel_id})
    assert context.roles.is_global_admin is False


def test_other_workspace_channel_admin_does_not_count(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """다른 workspace 채널의 관리자 자격은 이 문에서 세지 않는다.

    역할 적재가 채널을 workspace로 좁히지 않으면, 남의 workspace 관리자가
    이 workspace의 검수 표면에 그대로 선다.
    """
    first, second = workspace_ids
    user = _make_user(db, email="cross-ws-admin@example.com")
    _join(db, user=user, workspace_id=first)
    _join(db, user=user, workspace_id=second)
    channel_id = _make_channel(db, workspace_id=second, created_by=user.id)
    _make_channel_admin(db, channel_id=channel_id, user=user)

    with pytest.raises(HTTPException) as excinfo:
        resolve_reviewer_workspace(
            workspace_id=first, current_user=user, db=db
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "NOT_REVIEWER"


def test_other_workspace_owner_does_not_count(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """다른 workspace 문서의 담당자 자격은 이 문에서 세지 않는다.

    대상 판정은 문서 id 일치를 다시 보므로 남의 문서를 결정할 자리는 애초에
    없다. 그래도 적재를 좁혀야 하는 이유는 표면 게이트가 집합이 비었는지만
    보기 때문이다 — 좁히지 않으면 역할 하나 없는 workspace의 계류 목록이
    그 사람에게 그대로 열린다.
    """
    first, second = workspace_ids
    user = _make_user(db, email="cross-ws-owner@example.com")
    _join(db, user=user, workspace_id=first)
    _join(db, user=user, workspace_id=second)
    artifact_id = _make_artifact(db, workspace_id=second)
    _make_owner(db, artifact_id=artifact_id, user=user)

    with pytest.raises(HTTPException) as excinfo:
        resolve_reviewer_workspace(
            workspace_id=first, current_user=user, db=db
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "NOT_REVIEWER"

    # 대조군: 문서가 있는 쪽에서는 같은 사람이 그대로 통과한다. 403이
    # "경계가 막았다"는 뜻이지 "담당 행이 없다"는 뜻이 아님을 가른다.
    allowed = resolve_reviewer_workspace(
        workspace_id=second, current_user=user, db=db
    )
    assert allowed.roles.owned_artifact_ids == frozenset({artifact_id})


def test_artifact_owner_role_opens_the_surface(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """문서 담당자면 관리자가 아니어도 검수 표면에 선다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="artifact-owner@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    artifact_id = _make_artifact(db, workspace_id=workspace_id)
    _make_owner(db, artifact_id=artifact_id, user=user)

    context = resolve_reviewer_workspace(
        workspace_id=workspace_id, current_user=user, db=db
    )

    assert context.roles.owned_artifact_ids == frozenset({artifact_id})
    assert context.roles.has_any_role is True


def test_non_member_is_403(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """다른 workspace를 요청하면 권한이 있어도 소속에서 막힌다."""
    first, second = workspace_ids
    user = _make_user(db, email="outsider@example.com")
    _join(db, user=user, workspace_id=first)
    _grant(db, user=user, workspace_id=second)

    with pytest.raises(HTTPException) as excinfo:
        resolve_reviewer_workspace(
            workspace_id=second, current_user=user, db=db
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "NOT_MEMBER"


def test_authorization_denial_is_audited(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """인가 거부는 감사 스트림에 warning 한 줄로 남는다.

    `audit_log` 데코레이터는 핸들러 밖에서 난 예외를 보지 못한다. 거부가
    여기서 기록되지 않으면 감사 스트림은 통과한 결정만 담는다.
    """
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="audit-deny@example.com")
    _join(db, user=user, workspace_id=workspace_id)

    with patch(
        "catchup.server.wiki.dependencies.emit_audit_event"
    ) as emit:
        with pytest.raises(HTTPException):
            resolve_reviewer_workspace(
                workspace_id=workspace_id, current_user=user, db=db
            )

    assert emit.call_count == 1
    recorded = emit.call_args.kwargs
    assert recorded["action"] == KnowledgeReviewAction.AUTHORIZE
    assert recorded["status"] == AuditStatus.FAILURE
    assert recorded["level"] == AuditLevel.WARNING
    metadata = recorded["metadata"]
    assert metadata.context == "NOT_REVIEWER"
    assert metadata.user_id == user.id
    assert metadata.workspace_id == workspace_id


def test_reviewer_identifier_is_never_blank(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """판정자 식별자는 사용자 id로 채워지고 절대 비지 않는다.

    결정 저널의 DB CHECK가 빈 문자열을 거부하므로, 여기서 비면 승인이
    500으로 무너진다.
    """
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="journal@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    _grant(db, user=user, workspace_id=workspace_id)

    context = resolve_reviewer_workspace(current_user=user, db=db)

    assert context.reviewer == f"user:{user.id}"
    assert context.reviewer.strip() != ""


def test_uow_factory_binds_context_workspace(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """UoW는 컨텍스트가 정한 workspace로만 만들어진다.

    UoW 생성 시점의 workspace와 서비스 호출에 넘기는 workspace가 어긋나면
    충돌 표시가 남의 workspace 사실로 오염된다. 출처가 하나임을 못박는다.
    """
    workspace_id, other = workspace_ids
    user = _make_user(db, email="uow@example.com")
    context = ReviewerContext(
        user=user,
        workspace_id=workspace_id,
        reviewer=f"user:{user.id}",
        roles=_roles(is_global_admin=True),
    )

    uow = get_review_uow_factory(context)()

    assert uow._workspace_id == context.workspace_id
    assert uow._workspace_id != other


# ======================= 엔드포인트: 큐 =======================


def test_queue_requires_authentication(client: TestClient) -> None:
    """비로그인 요청은 401이고, 오류 계약을 지킨다.

    소비자가 가장 자주 만나는 오류가 세션 만료다. 그 응답만 detail이 사람이
    읽는 문자열이면 코드로 분기할 수 없으니, 여기서 모양까지 못박는다.
    """
    response = client.get("/api/v1/knowledge-review/queue")

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "code": "UNAUTHENTICATED",
        "message": "로그인이 필요합니다.",
    }


def test_authentication_error_hides_internal_reason(
    client: TestClient,
) -> None:
    """토큰이 유효하지 않은 경우도 같은 코드 하나로 알린다.

    쿠키 없음·만료·없는 사용자를 가려 알려 주면 로그인하지 않은 상대에게
    계정 존재 여부를 흘린다.
    """
    client.cookies.set("access_token", "not-a-real-token")

    response = client.get("/api/v1/knowledge-review/queue")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_queue_is_readable_by_member_without_any_role(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """역할이 하나도 없는 구성원도 목록을 볼 수 있고, can_review는 false다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="queue-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    item = ReviewQueueItem(
        proposal_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        title="오픈 API",
        status="pending",
        summary="속도 제한: rate_limit은 60이다",
        origin="compiled",
        contains_conflict=False,
        created_at=AT,
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.list_review_queue",
        return_value=ReviewQueuePage(items=(item,), total=1),
    ):
        response = client.get("/api/v1/knowledge-review/queue")

    assert response.status_code == 200
    assert response.json()["items"][0]["can_review"] is False


def test_queue_detail_is_readable_by_member_without_any_role(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """상세도 역할 없는 구성원에게 열리고, can_review는 false다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="detail-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    assert response.json()["can_review"] is False


def test_queue_denies_non_member(
    app: FastAPI,
    client: TestClient,
    db: Session,
    as_user: Callable[[User], None],
) -> None:
    """어느 workspace에도 속하지 않으면 목록부터 막힌다."""
    user = _make_user(db, email="queue-outsider@example.com")
    as_user(user)

    response = client.get("/api/v1/knowledge-review/queue")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_MEMBER"


def test_verdict_still_requires_reviewer_role(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """열람이 열려도 판정 경로는 역할 게이트를 그대로 지킨다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="verdict-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)

    response = client.put(
        _verdict_path(uuid.uuid4(), 1),
        json={"verdict": "approved", "block_content_hash": "sha256:x"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_REVIEWER"


@pytest.fixture
def reviewer(
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> User:
    """소속과 검토자 권한을 모두 갖춘 사용자를 로그인 상태로 만든다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="reviewer@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    _grant(db, user=user, workspace_id=workspace_id)
    as_user(user)
    return user


def test_queue_returns_page_shape(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """목록은 items·total·limit·offset 모양으로 나온다."""
    workspace_id, _ = workspace_ids
    item = ReviewQueueItem(
        proposal_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        title="오픈 API",
        status="pending",
        summary="속도 제한: rate_limit은 60이다",
        origin="compiled",
        contains_conflict=True,
        created_at=AT,
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
    page = ReviewQueuePage(items=(item,), total=7)

    with patch(
        "catchup.server.knowledge_review.api.list_review_queue",
        return_value=page,
    ) as service:
        response = client.get(
            "/api/v1/knowledge-review/queue",
            params={"limit": 1, "offset": 2, "contains_conflict": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 7
    assert data["limit"] == 1
    assert data["offset"] == 2
    assert len(data["items"]) == 1
    returned = data["items"][0]
    assert datetime.fromisoformat(returned.pop("created_at")) == AT
    assert returned == {
        "proposal_id": str(item.proposal_id),
        "status": "pending",
        "artifact": {
            "id": str(item.artifact_id),
            "title": "오픈 API",
            "channel_id": None,
            "folder_id": None,
        },
        "summary": "속도 제한: rate_limit은 60이다",
        "origin": "compiled",
        "contains_conflict": True,
        "owners": [],
        "can_review": True,
    }
    assert service.call_args.kwargs == {
        "workspace_id": workspace_id,
        "contains_conflict": True,
        "artifact_ids": None,
        "created_after": None,
        "created_before": None,
        "limit": 1,
        "offset": 2,
    }


def test_queue_filters_narrow_artifact_ids(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """채널·담당자 조건은 문서 id 집합으로 바뀌어 서비스에 들어간다."""
    workspace_id, _ = workspace_ids
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=reviewer.id
    )
    both = _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    _make_artifact(db, workspace_id=workspace_id, channel_id=channel_id)
    owner_only = _make_artifact(db, workspace_id=workspace_id)
    _make_owner(db, artifact_id=both, user=reviewer)
    _make_owner(db, artifact_id=owner_only, user=reviewer)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
    page = ReviewQueuePage(items=(), total=0)

    with patch(
        "catchup.server.knowledge_review.api.list_review_queue",
        return_value=page,
    ) as service:
        response = client.get(
            "/api/v1/knowledge-review/queue",
            params={
                "channel_id": str(channel_id),
                "owner_user_id": reviewer.id,
                "created_after": "2026-08-01T00:00:00+00:00",
                "created_before": "2026-08-31T00:00:00+00:00",
            },
        )

    assert response.status_code == 200
    kwargs = service.call_args.kwargs
    assert kwargs["artifact_ids"] == frozenset({both})
    assert kwargs["created_after"] == datetime(
        2026, 8, 1, tzinfo=timezone.utc
    )
    assert kwargs["created_before"] == datetime(
        2026, 8, 31, tzinfo=timezone.utc
    )


def test_queue_carries_location_owners_and_can_review(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """항목마다 문서 위치·담당자·결정 가능 여부를 함께 싣는다."""
    workspace_id, _ = workspace_ids
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=reviewer.id
    )
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    other = _make_user(db, email="queue-owner@example.com")
    _join(db, user=other, workspace_id=workspace_id)
    _make_owner(db, artifact_id=artifact_id, user=other)
    item = ReviewQueueItem(
        proposal_id=uuid.uuid4(),
        artifact_id=artifact_id,
        title="오픈 API",
        status="pending",
        summary="속도 제한: rate_limit은 60이다",
        origin="compiled",
        contains_conflict=False,
        created_at=AT,
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
    page = ReviewQueuePage(items=(item,), total=1)

    with patch(
        "catchup.server.knowledge_review.api.list_review_queue",
        return_value=page,
    ):
        response = client.get("/api/v1/knowledge-review/queue")

    assert response.status_code == 200
    returned = response.json()["items"][0]
    assert returned["artifact"]["channel_id"] == str(channel_id)
    assert returned["artifact"]["folder_id"] is None
    assert [owner["user_id"] for owner in returned["owners"]] == [other.id]
    # 담당자가 있는 문서는 담당자만 결정한다. 전역 관리자 폴백이 서지 않는다.
    assert returned["can_review"] is False


def test_queue_rejects_out_of_range_limit(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """limit 상한을 넘는 요청은 서비스에 닿지 않는다."""
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    response = client.get(
        "/api/v1/knowledge-review/queue", params={"limit": 201}
    )

    assert response.status_code == 422


# ======================= 엔드포인트: 상세 =======================


def test_detail_returns_blocks_read_set_and_conflicts(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """상세는 본문·근거 장부와 다툼 블록이 가리키는 충돌을 함께 싣는다.

    충돌 목록은 블록의 proposal_ids로만 모은다. subject_key로 모으던 옛
    경로와 달리, 표시(contains_conflict)와 목록이 같은 사실 하나에서
    나오므로 둘이 어긋날 자리가 없다.
    """
    workspace_id, _ = workspace_ids
    proposal_id = uuid.uuid4()
    conflict_id = uuid.uuid4()
    other_conflict_id = uuid.uuid4()
    claim_id = uuid.uuid4()
    loser_claim_id = uuid.uuid4()
    stored = _contested_proposal(
        proposal_id=proposal_id,
        contradiction_id=conflict_id,
        winner_claim_id=claim_id,
        loser_claim_id=loser_claim_id,
    )
    contradiction = StoredContradictionProposal(
        id=conflict_id,
        predicate="rate_limit",
        subject_key=f"node:{stored.subject_node_id}",
        summary="rate_limit 값이 갈렸다",
        values=(
            StoredContradictionValue(
                claim_id=claim_id,
                value=60,
                normalized="60",
                statement="rate_limit은 60이다",
                observed_at=None,
            ),
        ),
    )
    other = StoredContradictionProposal(
        id=other_conflict_id,
        predicate="owner",
        subject_key="node:other",
        summary="남의 대상 모순",
        values=(),
    )
    mutations = _FakeMutations(pending=(contradiction, other))
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored), mutations=mutations
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["contains_conflict"] is True
    assert data["blocks"][0]["claim_ids"] == [
        str(claim_id),
        str(loser_claim_id),
    ]
    assert data["read_set"] == {
        "claim_ids": [str(claim_id), str(loser_claim_id)],
        "proposal_ids": [str(conflict_id)],
        "relation_ids": [],
    }
    assert [item["proposal_id"] for item in data["conflicts"]] == [
        str(conflict_id)
    ]
    assert data["conflicts"][0]["values"] == [
        {
            "claim_id": str(claim_id),
            "value": 60,
            "statement": "rate_limit은 60이다",
        }
    ]
    # 모든 조회가 컨텍스트의 workspace 하나로만 나갔다.
    assert set(mutations.workspace_ids) == {workspace_id}


def test_detail_blocks_carry_sources(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """블록에 붙은 근거 인용이 상세 응답에 그대로 실린다."""
    proposal_id = uuid.uuid4()
    claim_id = uuid.uuid4()
    stored = _proposal(
        proposal_id=proposal_id,
        claim_id=claim_id,
        sources=(
            BlockSource(
                claim_id=claim_id,
                statement="rate_limit은 60이다",
                observed_at=AT,
                citation_verified=True,
            ),
        ),
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    assert response.json()["blocks"][0]["sources"] == [
        {
            "claim_id": str(claim_id),
            "statement": "rate_limit은 60이다",
            "observed_at": AT.isoformat().replace("+00:00", "Z"),
            "citation_verified": True,
        }
    ]


def test_detail_blocks_without_sources_return_empty_list(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """근거 인용 없이 만들어진 옛 블록은 빈 목록으로 나간다."""
    proposal_id = uuid.uuid4()
    stored = _proposal(proposal_id=proposal_id)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    assert response.json()["blocks"][0]["sources"] == []


def test_detail_relation_block_carries_relation_ids(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """relation_section 블록의 관계 장부가 블록과 Read Set에 함께 실린다.

    이 블록의 근거는 relation_ids 하나뿐이라, 이것이 빠지면 검토자는
    근거가 전혀 없는 문장을 보게 된다.
    """
    proposal_id = uuid.uuid4()
    relation_id = uuid.uuid4()
    stored = _relation_proposal(
        proposal_id=proposal_id, relation_id=relation_id
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["blocks"][0]["relation_ids"] == [str(relation_id)]
    assert data["blocks"][0]["claim_ids"] == []
    assert data["read_set"] == {
        "claim_ids": [],
        "proposal_ids": [],
        "relation_ids": [str(relation_id)],
    }


def _revision_blocks(
    *, claim_id: uuid.UUID, body: str
) -> tuple[ArtifactBlock, ...]:
    """발행판에 저장할 블록 한 벌을 만든다."""
    return (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="속도 제한",
            body=body,
            claim_ids=(claim_id,),
            proposal_ids=(),
            ontology_version="v1",
        ),
    )


def _seed_revision(
    db: Session,
    *,
    workspace_id: int,
    artifact_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
) -> uuid.UUID:
    """문서의 1판을 그 판을 낳은 승인된 변경안과 함께 넣는다.

    판 행은 자기를 낳은 변경안을 가리켜야 하고, 그 변경안은 결정 저널
    (검토자·결정 시각)이 채워진 승인 상태여야 한다. DB CHECK가 그것을
    요구하므로 여기서도 같은 모양으로 넣는다.
    """
    source_proposal_id = uuid.uuid4()
    db.add(
        KnowledgeArtifactChangeProposal(
            id=source_proposal_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            blocks=serialize_blocks(blocks),
            status="approved",
            content_hash=blocks_content_hash(blocks),
            idempotency_key=f"seed:{source_proposal_id}",
            base_revision_id=None,
            reviewed_at=AT,
            reviewer="test:seed",
        )
    )
    db.flush()
    revision_id = uuid.uuid4()
    db.add(
        KnowledgeArtifactRevision(
            id=revision_id,
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            revision_number=1,
            blocks=serialize_blocks(blocks),
            source_proposal_id=source_proposal_id,
        )
    )
    db.flush()
    return revision_id


def _two_block_proposal(
    *,
    proposal_id: uuid.UUID,
    artifact_id: uuid.UUID,
    claim_id: uuid.UUID,
    body: str,
) -> StoredArtifactProposal:
    """발행판 블록 하나를 고치고 블록 하나를 더한 변경안을 만든다."""
    return StoredArtifactProposal(
        id=proposal_id,
        artifact_id=artifact_id,
        subject_node_id=uuid.uuid4(),
        title="오픈 API",
        status="pending",
        blocks=(
            ArtifactBlock(
                block_kind=BLOCK_KIND_CLAIM_SECTION,
                heading="속도 제한",
                body=body,
                claim_ids=(claim_id,),
                proposal_ids=(),
                ontology_version="v1",
            ),
            ArtifactBlock(
                block_kind=BLOCK_KIND_CLAIM_SECTION,
                heading="담당",
                body="담당은 플랫폼 팀이다",
                claim_ids=(uuid.uuid4(),),
                proposal_ids=(),
                ontology_version="v1",
            ),
        ),
        content_hash="hash",
        base_revision_id=None,
        rejection_reason=None,
        origin="compiled",
        created_at=AT,
    )


def test_detail_is_readable_by_member_without_document_role_but_can_review_false(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """워크스페이스 역할이 하나라도 있으면 200이고 can_review는 False다.

    열람과 판정을 나눈다. 남의 채널 문서라도 검토자는 내용을 읽을 수
    있어야 하고, 결정 버튼만 잠기면 된다.
    """
    workspace_id, _ = workspace_ids
    outsider = _make_user(db, email="other-channel-admin@example.com")
    _join(db, user=outsider, workspace_id=workspace_id)
    own_channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=outsider.id
    )
    _make_channel_admin(db, channel_id=own_channel_id, user=outsider)
    other_channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=outsider.id
    )
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, channel_id=other_channel_id
    )
    owner = _make_user(db, email="detail-owner@example.com")
    _join(db, user=owner, workspace_id=workspace_id)
    _make_owner(db, artifact_id=artifact_id, user=owner)
    as_user(outsider)

    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["can_review"] is False
    assert [item["user_id"] for item in data["owners"]] == [owner.id]
    assert data["artifact"]["channel_id"] == str(other_channel_id)


def test_detail_embeds_base_blocks_and_block_changes(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """발행판이 있으면 base_blocks가 실리고 block_changes가 백엔드 계산으로 온다."""
    workspace_id, _ = workspace_ids
    artifact_id = _make_artifact(db, workspace_id=workspace_id)
    claim_id = uuid.uuid4()
    _seed_revision(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        blocks=_revision_blocks(claim_id=claim_id, body="rate_limit은 60이다"),
    )
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_two_block_proposal(
                proposal_id=proposal_id,
                artifact_id=artifact_id,
                claim_id=claim_id,
                body="rate_limit은 120이다",
            )
        )
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["can_review"] is True
    assert [
        (item["block_index"], item["body"]) for item in data["base_blocks"]
    ] == [(0, "rate_limit은 60이다")]
    assert data["block_changes"] == [
        {"change": "modified", "block_index": 0, "base_block_index": 0},
        {"change": "added", "block_index": 1, "base_block_index": None},
    ]
    assert data["blocks"][0]["change_reason"] == "산문 표현만 다듬었습니다."
    assert data["blocks"][1]["change_reason"] == "새로 추가된 섹션입니다."
    assert data["blocks"][0]["markdown"].startswith("## 속도 제한")


def test_detail_marks_evidence_swap_as_modified(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """본문이 같고 근거만 갈린 블록도 검토 상세에 변경으로 나타난다.

    발행은 변경 목록에 없는 블록의 결정 요구를 면제하므로, 근거 교체가
    화면에 뜨지 않으면 사람이 결정할 자리 자체가 사라진다.
    """
    workspace_id, _ = workspace_ids
    artifact_id = _make_artifact(db, workspace_id=workspace_id)
    claim_id = uuid.uuid4()
    _seed_revision(
        db,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        blocks=_revision_blocks(claim_id=claim_id, body="rate_limit은 60이다"),
    )
    proposal_id = uuid.uuid4()
    # 같은 claim을 가리키면서 인용만 새로 붙었다. claim 개수가 그대로라
    # 개수를 세는 문구로는 무엇이 달라졌는지 말할 수 없다.
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_proposal(
                proposal_id=proposal_id,
                artifact_id=artifact_id,
                claim_id=claim_id,
                sources=(
                    BlockSource(
                        claim_id=claim_id,
                        statement="rate_limit은 60이다",
                        observed_at=AT,
                        citation_verified=True,
                    ),
                ),
            )
        )
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["block_changes"] == [
        {"change": "modified", "block_index": 0, "base_block_index": 0},
    ]
    assert (
        data["blocks"][0]["change_reason"]
        == "본문은 그대로이고 근거가 갈렸습니다."
    )


def test_detail_without_revision_has_empty_base_blocks(
    app: FastAPI,
    client: TestClient,
    db: Session,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """발행판이 없는 문서는 base_blocks가 비고 모든 블록이 새 블록이다.

    문서 전체가 새것이므로 블록마다 붙는 수정 이유는 내려보내지 않는다.
    """
    workspace_id, _ = workspace_ids
    artifact_id = _make_artifact(db, workspace_id=workspace_id)
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_two_block_proposal(
                proposal_id=proposal_id,
                artifact_id=artifact_id,
                claim_id=uuid.uuid4(),
                body="rate_limit은 120이다",
            )
        )
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["base_blocks"] == []
    assert [item["change"] for item in data["block_changes"]] == [
        "added",
        "added",
    ]
    assert [item["change_reason"] for item in data["blocks"]] == [None, None]


def test_detail_missing_proposal_returns_404(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """이 workspace에 없는 변경안은 404다."""
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    response = client.get(
        f"/api/v1/knowledge-review/queue/{uuid.uuid4()}"
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"


def test_detail_conflict_flag_follows_contested_blocks(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """다툼 블록이 없으면 대상에 모순이 걸려 있어도 표시하지 않는다.

    옛 경로는 대상 노드로 표시하고 목록은 subject_key로 모아, 표시는
    켜졌는데 목록은 빈 상태가 나올 수 있었다. 이제 둘 다 블록에서
    나오므로 그 어긋남이 재현되지 않는다.
    """
    proposal_id = uuid.uuid4()
    stored = _proposal(proposal_id=proposal_id)
    contradiction = StoredContradictionProposal(
        id=uuid.uuid4(),
        predicate="rate_limit",
        subject_key=f"node:{stored.subject_node_id}",
        summary="rate_limit 값이 갈렸다",
        values=(),
    )
    mutations = _FakeMutations(
        pending=(contradiction,),
        subject_pending=(
            StoredPendingProposal(
                id=contradiction.id,
                proposal_kind="contradiction",
                summary="rate_limit 값이 갈렸다",
                resolver_metadata={},
            ),
        ),
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored), mutations=mutations
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["contains_conflict"] is False
    assert data["conflicts"] == []


def test_detail_contested_block_carries_variants_only(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """다툼 블록은 후보만 싣고 블록 sources를 겹쳐 싣지 않는다."""
    proposal_id = uuid.uuid4()
    winner = uuid.uuid4()
    loser = uuid.uuid4()
    stored = _contested_proposal(
        proposal_id=proposal_id,
        contradiction_id=uuid.uuid4(),
        winner_claim_id=winner,
        loser_claim_id=loser,
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    block = response.json()["blocks"][0]
    assert block["block_index"] == 0
    assert block["block_content_hash"] == block_content_hash(
        stored.blocks[0]
    )
    assert block["sources"] == []
    assert [variant["claim_id"] for variant in block["variants"]] == [
        str(winner),
        str(loser),
    ]
    assert block["variants"][0]["sources"] == [
        {
            "claim_id": str(winner),
            "statement": "rate_limit은 60이다",
            "observed_at": AT.isoformat().replace("+00:00", "Z"),
            "citation_verified": True,
        }
    ]


def test_detail_plain_block_has_no_variants(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """다툼이 아닌 블록의 variants는 없음(null)으로 나간다."""
    proposal_id = uuid.uuid4()
    stored = _proposal(proposal_id=proposal_id)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    assert response.json()["blocks"][0]["variants"] is None


def test_detail_block_carries_recorded_verdict(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """이미 내려진 블록 결정이 상세 응답에 함께 실린다.

    검토자가 화면을 다시 열었을 때 자기가 무엇을 눌렀는지 보이지 않으면,
    같은 블록을 다시 판정하거나 미결정으로 착각한다.
    """
    proposal_id = uuid.uuid4()
    stored = _proposal(proposal_id=proposal_id)
    verdict = StoredBlockVerdict(
        proposal_id=proposal_id,
        block_index=0,
        block_content_hash=block_content_hash(stored.blocks[0]),
        verdict="rejected",
        rejection_reason="근거가 부족하다",
        chosen_winner_claim_id=None,
        reviewer="user:1",
        reviewed_at=AT,
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored),
        verdicts=_FakeBlockVerdicts(stored=(verdict,)),
    )

    response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 200
    recorded = response.json()["blocks"][0]["verdict"]
    assert recorded["verdict"] == "rejected"
    assert recorded["rejection_reason"] == "근거가 부족하다"
    assert recorded["block_index"] == 0
    assert recorded["reviewer"] == "user:1"


# ======================= workspace 경계 =======================
#
# 여기만 실 UnitOfWork를 쓴다. 경계를 지키는 것은 저장소 질의의 where 절이라,
# 대역으로 바꾸면 그 절이 빠져도 테스트가 통과한다. `SessionLocal`만 테스트
# 연결로 바꿔치기해 `get_review_uow_factory`의 workspace 결정 경로는 실제
# 코드가 그대로 돌게 둔다.


def _seed_definition(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    admin_user_id: int | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """문서가 딛고 설 채널과 정의를 실 DB에 심는다.

    문서 행은 정의에 매여 있어, 계류 변경안 하나를 심으려면 정의가 먼저
    서 있어야 한다. 돌려주는 것은 (정의, 채널)이다.

    정의가 만든 문서는 그 채널에 놓이므로 검수 권한도 채널 관리자에게
    간다. 전역 ADMIN은 미분류 문서의 폴백일 뿐이라 채널에 놓인 문서에는
    서지 않는다. 그래서 검수까지 가는 시험은 `admin_user_id`로 그 채널의
    관리자를 함께 세운다.
    """
    with session_factory() as session:
        created_by = session.execute(
            select(User.id).order_by(User.id).limit(1)
        ).scalar()
        if created_by is None:
            pytest.skip("user가 없어 통합 테스트를 건너뛴다.")
        channel_id = _make_channel(
            session, workspace_id=workspace_id, created_by=created_by
        )
        definition_id = uuid.uuid4()
        session.add(
            ArtifactDefinition(
                id=definition_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind="entity_summary",
                selection_spec={
                    "entity_filter": {"entity_types": ["feature"]},
                    "relation_paths": [],
                    "predicate_sections": None,
                },
                created_by=created_by,
            )
        )
        if admin_user_id is not None:
            session.add(
                ChannelAdmin(channel_id=channel_id, user_id=admin_user_id)
            )
        session.commit()
    return definition_id, channel_id


def _seed_pending_proposal(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    admin_user_id: int | None = None,
) -> uuid.UUID:
    """어느 workspace에 계류 변경안 하나를 실 DB로 심는다."""
    node_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            KnowledgeNode(
                id=node_id,
                workspace_id=workspace_id,
                node_kind="entity",
                entity_type="feature",
                canonical_key=f"test:review-api:{uuid.uuid4().hex}",
                display_name="속도 제한 기능",
            )
        )
        session.commit()

    blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="rate_limit",
            body="rate_limit은 60이다",
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="1",
        ),
    )
    content_hash = blocks_content_hash(blocks)
    definition_id, channel_id = _seed_definition(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=admin_user_id,
    )
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition_id,
            channel_id=channel_id,
            kind="entity_summary",
            subject_node_id=node_id,
            title="오픈 API",
        )
        proposal_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=blocks,
            content_hash=content_hash,
            idempotency_key=artifact_idempotency_key(
                artifact_id, content_hash, base_revision_id=None
            ),
            base_revision_id=None,
        )
        uow.commit()
    return proposal_id


def _real_session_local(
    session_factory: Callable[[], Session],
) -> Any:
    """실 UnitOfWork가 테스트 트랜잭션 위에서 돌게 바꿔치기한다."""
    return patch(
        "catchup.server.knowledge_review.dependencies.SessionLocal",
        session_factory,
    )


def test_detail_hides_other_workspace_proposal(
    app: FastAPI,
    client: TestClient,
    db: Session,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """다른 workspace의 변경안은 상세로 볼 수 없다.

    대조군을 함께 둔다. 그 workspace의 검토자에게는 같은 식별자가 200으로
    보여야, 404가 "경계가 막았다"는 뜻이지 "그런 안건이 애초에 없다"는 뜻이
    아님이 증명된다.
    """
    first, second = workspace_ids
    insider = _make_user(db, email="ws-insider@example.com")
    _join(db, user=insider, workspace_id=second)
    _grant(db, user=insider, workspace_id=second)
    proposal_id = _seed_pending_proposal(
        session_factory, workspace_id=second, admin_user_id=insider.id
    )

    as_user(insider)
    with _real_session_local(session_factory):
        allowed = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert allowed.status_code == 200
    assert allowed.json()["proposal_id"] == str(proposal_id)

    outsider = _make_user(db, email="ws-outsider@example.com")
    _join(db, user=outsider, workspace_id=first)
    _grant(db, user=outsider, workspace_id=first)
    as_user(outsider)
    with _real_session_local(session_factory):
        response = client.get(f"/api/v1/knowledge-review/queue/{proposal_id}")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"


def test_approve_rejects_other_workspace_proposal(
    app: FastAPI,
    client: TestClient,
    db: Session,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """다른 workspace의 변경안은 승인할 수도 없다.

    결정은 되돌릴 수 없으므로, 404를 받는 것만으로는 부족하다. 뒤에 그
    변경안이 여전히 계류 상태인지도 확인해 아무것도 쓰이지 않았음을 본다.
    """
    first, second = workspace_ids
    proposal_id = _seed_pending_proposal(session_factory, workspace_id=second)
    outsider = _make_user(db, email="ws-approve@example.com")
    _join(db, user=outsider, workspace_id=first)
    _grant(db, user=outsider, workspace_id=first)
    as_user(outsider)

    with _real_session_local(session_factory):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=second
    ) as uow:
        untouched = uow.artifacts.get_proposal(proposal_id=proposal_id)
    assert untouched is not None
    assert untouched.status == "pending"


# ======================= 대상 판정: 담당자·관리자 =======================
#
# 여기가 확정 기획 5.3 매트릭스의 검수 축이다. 담당자는 자기 문서만, 관리자는
# 담당자 없는 문서의 폴백만, 미분류 문서의 폴백은 전역 ADMIN이다. 판정 규칙
# 자체는 test_wiki_roles.py가 순수 함수로 보고, 여기서는 라우터가 실제 DB
# 행(artifact_owners·channel_admins·users.role)에서 그 판정을 세우는지 본다.


def _approve(client: TestClient, proposal_id: uuid.UUID):
    """승인 엔드포인트를 부른다."""
    return client.post(
        f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
    )


def test_owner_can_approve_own_artifact_proposal(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """담당자는 자기 문서의 변경안을 결정한다.

    문서를 채널 아래에 두고 그 채널 관리자는 아닌 사람을 세운다. 통과가
    관리자 폴백이 아니라 담당자 자격에서 나왔음을 이걸로 가른다.
    """
    workspace_id, _ = workspace_ids
    owner = _make_user(db, email="doc-owner@example.com")
    _join(db, user=owner, workspace_id=workspace_id)
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=owner.id
    )
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    _make_owner(db, artifact_id=artifact_id, user=owner)
    as_user(owner)

    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )
    result = ReviewResult(
        proposal_id=proposal_id,
        verdict="approved",
        revision_id=uuid.uuid4(),
        revision_number=1,
        claims_accepted=1,
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        return_value=result,
    ) as service:
        response = _approve(client, proposal_id)

    assert response.status_code == 200
    assert service.call_args.kwargs["reviewer"] == f"user:{owner.id}"


def test_admin_cannot_decide_when_owner_exists(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """담당자가 있는 문서는 채널 관리자라도 만지지 못한다.

    관리자는 폴백이지 상위 권한이 아니다. 여기서 통과하면 담당자의 결정
    영역을 관리자가 언제든 덮어쓸 수 있게 된다.
    """
    workspace_id, _ = workspace_ids
    admin = _make_user(db, email="channel-admin-blocked@example.com")
    owner = _make_user(db, email="other-owner@example.com")
    _join(db, user=admin, workspace_id=workspace_id)
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=admin.id
    )
    _make_channel_admin(db, channel_id=channel_id, user=admin)
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    _make_owner(db, artifact_id=artifact_id, user=owner)
    as_user(admin)

    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal"
    ) as service:
        response = _approve(client, proposal_id)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_DOCUMENT_REVIEWER"
    service.assert_not_called()


def test_channel_admin_decides_unowned_artifact(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """담당자 없는 채널 문서는 그 채널 관리자가 결정한다."""
    workspace_id, _ = workspace_ids
    admin = _make_user(db, email="channel-admin-ok@example.com")
    _join(db, user=admin, workspace_id=workspace_id)
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=admin.id
    )
    _make_channel_admin(db, channel_id=channel_id, user=admin)
    artifact_id = _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    as_user(admin)

    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )
    result = ReviewResult(
        proposal_id=proposal_id,
        verdict="approved",
        revision_id=uuid.uuid4(),
        revision_number=1,
        claims_accepted=1,
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        return_value=result,
    ):
        response = _approve(client, proposal_id)

    assert response.status_code == 200


def test_global_admin_decides_unassigned_artifact(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """채널에 놓이지 않은 문서의 폴백은 전역 ADMIN이다.

    같은 전역 ADMIN이 채널에 놓인 문서에서는 막히는 것까지 함께 본다 —
    전역 역할이 채널 관리자 자리를 대신하지 않는다.
    """
    workspace_id, _ = workspace_ids
    admin = _make_user(db, email="global-admin@example.com")
    _join(db, user=admin, workspace_id=workspace_id)
    admin.role = UserRole.ADMIN
    db.flush()
    unassigned_id = _make_artifact(db, workspace_id=workspace_id)
    channel_id = _make_channel(
        db, workspace_id=workspace_id, created_by=admin.id
    )
    in_channel_id = _make_artifact(
        db, workspace_id=workspace_id, channel_id=channel_id
    )
    as_user(admin)

    unassigned_proposal = uuid.uuid4()
    channel_proposal = uuid.uuid4()
    proposals = {
        unassigned_proposal: unassigned_id,
        channel_proposal: in_channel_id,
    }

    # 요청 두 번이 서로 다른 문서를 가리켜야 해서, 지금 볼 안건을 담는
    # 칸을 하나 두고 대역이 그때그때 그 안건을 돌려주게 한다.
    current = [unassigned_proposal]

    def override() -> Callable[[], _FakeUow]:
        return _fake_factory(
            artifacts=_FakeArtifacts(
                proposal=_proposal(
                    proposal_id=current[0],
                    artifact_id=proposals[current[0]],
                )
            )
        )

    app.dependency_overrides[get_review_uow_factory] = override
    result = ReviewResult(
        proposal_id=unassigned_proposal,
        verdict="approved",
        revision_id=uuid.uuid4(),
        revision_number=1,
        claims_accepted=1,
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        return_value=result,
    ):
        allowed = _approve(client, unassigned_proposal)

    assert allowed.status_code == 200

    current[0] = channel_proposal
    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal"
    ) as service:
        blocked = _approve(client, channel_proposal)

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "NOT_DOCUMENT_REVIEWER"
    service.assert_not_called()


def test_member_without_roles_gets_403_not_reviewer(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """역할이 하나도 없으면 대상 판정에 닿기 전에 막힌다.

    두 겹의 인가가 각자 다른 코드로 갈리는지 본다 — 표면 자격은
    NOT_REVIEWER, 문서 자격은 NOT_DOCUMENT_REVIEWER다.
    """
    workspace_id, _ = workspace_ids
    member = _make_user(db, email="plain-member@example.com")
    _join(db, user=member, workspace_id=workspace_id)
    artifact_id = _make_artifact(db, workspace_id=workspace_id)
    as_user(member)

    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=_proposal(
                proposal_id=proposal_id, artifact_id=artifact_id
            )
        )
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal"
    ) as service:
        response = _approve(client, proposal_id)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_REVIEWER"
    service.assert_not_called()


# ======================= 표면에 없는 운영 경로 =======================
#
# 모순 직접 판정(resolve)과 적용(apply)은 기획 UX에 없는 운영 도구라
# 정식 API에서 뺐다. 그 경로는 debug 라우터와 evaluation CLI 러너가
# 담당한다. 아래 둘은 "다시 붙지 않았다"를 고정한다 — 서비스는 그대로
# 남아 있어 라우터 한 줄이면 표면이 되살아난다.


def test_operator_routes_are_absent_from_router() -> None:
    """정식 라우터에 resolve·apply 경로가 없다."""
    paths = {
        getattr(route, "path", None) for route in router.routes
    }

    assert "/api/v1/knowledge-review/apply" not in paths
    assert not any(
        path is not None
        and (path.endswith("/resolve") or "/apply/" in path)
        for path in paths
    )


def test_operator_routes_return_404_when_called(
    client: TestClient, reviewer: User
) -> None:
    """인증을 붙여 불러도 404다.

    권한 거부(403)가 아니라 없음(404)이어야 한다. 403이면 그 경로가
    아직 서 있고 게이트만 닫힌 것이다.
    """
    proposal_id = uuid.uuid4()

    resolve = client.post(
        f"/api/v1/knowledge-review/contradictions/{proposal_id}/resolve",
        json={"winner_claim_id": str(uuid.uuid4())},
    )
    apply_all = client.post("/api/v1/knowledge-review/apply")
    apply_one = client.post(
        f"/api/v1/knowledge-review/apply/{proposal_id}"
    )

    assert resolve.status_code == 404
    assert apply_all.status_code == 404
    assert apply_one.status_code == 404


# ======================= 엔드포인트: 결정 =======================


def test_approve_records_current_user_as_reviewer(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """승인은 판정자로 지금 로그인한 사용자를 넘긴다."""
    proposal_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )
    result = ReviewResult(
        proposal_id=proposal_id,
        verdict="approved",
        revision_id=revision_id,
        revision_number=3,
        claims_accepted=2,
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        return_value=result,
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 200
    assert response.json() == {
        "proposal_id": str(proposal_id),
        "verdict": "approved",
        "revision_id": str(revision_id),
        "revision_number": 3,
        "claims_accepted": 2,
    }
    assert service.call_args.kwargs["reviewer"] == f"user:{reviewer.id}"
    assert service.call_args.kwargs["verdict"] == "approved"


def test_approve_audit_records_proposal_id(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """승인 감사 기록에는 어느 안건을 결정했는지가 남는다.

    무엇을 승인했는지 없는 기록은 "누가 언제"만 남아 결정을 되짚을 수
    없다.
    """
    workspace_id, _ = workspace_ids
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )
    result = ReviewResult(
        proposal_id=proposal_id,
        verdict="approved",
        revision_id=uuid.uuid4(),
        revision_number=1,
        claims_accepted=1,
    )

    with (
        patch(
            "catchup.server.knowledge_review.api.review_artifact_proposal",
            return_value=result,
        ),
        patch("catchup.audit.utils.emit_audit_event") as emit,
    ):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 200
    recorded = emit.call_args.kwargs
    assert recorded["action"] == KnowledgeReviewAction.APPROVE
    assert recorded["status"] == AuditStatus.SUCCESS
    assert recorded["metadata"].proposal_id == str(proposal_id)
    assert recorded["metadata"].workspace_id == workspace_id


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (
            "CONTESTED_REQUIRES_BLOCK_REVIEW",
            "다툼 블록이 있어 블록 검토를 거쳐야 합니다.",
        ),
        (
            "BLOCK_REVIEW_IN_PROGRESS",
            "블록 검토가 시작된 변경안은 발행으로 끝내야 합니다.",
        ),
    ],
)
def test_approve_relays_service_block_review_codes(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    code: str,
    message: str,
) -> None:
    """통짜 승인 가드는 서비스가 갖고, 라우터는 코드를 409로 옮긴다.

    같은 검사를 라우터가 또 하면 정식 API·debug·CLI 세 표면의 규칙이
    갈라진다. 그래서 여기서 확인하는 것은 옮기기뿐이다. 예외 문구는
    내부 사정을 담고 있어 응답에 새어 나오지 않아야 한다.
    """
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        side_effect=ProposalReviewError(
            f"변경안 {proposal_id}는 확정할 수 없다", code=code
        ),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == code
    assert response.json()["detail"]["message"] == message
    assert "확정할 수 없다" not in response.text


def test_approve_with_contested_block_requires_block_review(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """다툼 블록이 있는 변경안은 통짜 승인으로 확정할 수 없다.

    통짜 승인은 승자를 고르는 자리가 없다. 그대로 태우면 사람이 고르지
    않은 값이 문서에 실리므로, 블록 검토를 거치라고 돌려보낸다. 막는 것은
    서비스이고, 이 테스트는 라우터를 거친 응답까지 그대로 나오는지 본다.
    """
    proposal_id = uuid.uuid4()
    stored = _contested_proposal(
        proposal_id=proposal_id,
        contradiction_id=uuid.uuid4(),
        winner_claim_id=uuid.uuid4(),
        loser_claim_id=uuid.uuid4(),
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    response = client.post(
        f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]["code"] == "CONTESTED_REQUIRES_BLOCK_REVIEW"
    )


def test_reject_passes_reason(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """반려는 사유를 그대로 서비스에 넘긴다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )
    result = ReviewResult(
        proposal_id=proposal_id,
        verdict="rejected",
        revision_id=None,
        revision_number=None,
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        return_value=result,
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/reject",
            json={"reason": "근거가 부족하다"},
        )

    assert response.status_code == 200
    assert response.json()["verdict"] == "rejected"
    assert service.call_args.kwargs["reason"] == "근거가 부족하다"


def test_reject_without_reason_is_400(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """공백뿐인 사유는 서비스에 닿기 전에 막는다."""
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal"
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{uuid.uuid4()}/reject",
            json={"reason": "   "},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "REASON_REQUIRED"
    service.assert_not_called()


def test_already_decided_returns_409_with_code(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """이미 결정된 변경안은 409 ALREADY_DECIDED다.

    실패 감사 기록에도 그 code가 남는지 함께 본다. `audit_log`는 예외의
    `code` 속성만 읽으므로, detail에만 코드가 있으면 감사 스트림에는
    "승인이 실패했다"만 남고 이유가 사라진다.
    """
    proposal_id = uuid.uuid4()
    stored = _proposal(proposal_id=proposal_id, status="approved")
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    with (
        patch(
            "catchup.server.knowledge_review.api.review_artifact_proposal",
            side_effect=ProposalReviewError("변경안은 이미 approved 상태다"),
        ),
        patch("catchup.audit.utils.emit_audit_event") as emit,
    ):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "ALREADY_DECIDED",
        "message": "이미 결정된 변경안입니다.",
    }
    recorded = emit.call_args.kwargs
    assert recorded["status"] == AuditStatus.FAILURE
    assert recorded["metadata"].context == "ALREADY_DECIDED"
    assert recorded["metadata"].proposal_id == str(proposal_id)


def test_stale_base_revision_returns_409_with_code(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """딛고 선 판이 낡았으면 409 STALE_BASE_REVISION이다."""
    proposal_id = uuid.uuid4()
    stored = _proposal(proposal_id=proposal_id, base_revision_id=None)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(
            proposal=stored, latest=(uuid.uuid4(), 4)
        )
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        side_effect=ProposalReviewError("딛고 선 판이 최신이 아니다"),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "STALE_BASE_REVISION"


def test_decision_error_hides_internal_message(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """예외 문자열은 응답에 실리지 않는다."""
    proposal_id = uuid.uuid4()
    secret = "내부 사정: 저장소 제약 이름"
    stored = _proposal(proposal_id=proposal_id, status="rejected")
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=stored)
    )

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        side_effect=ProposalReviewError(secret),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert response.status_code == 409
    assert secret not in response.text


def test_missing_proposal_decision_returns_404(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """없는 변경안에 대한 결정은 409가 아니라 404다."""
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.review_artifact_proposal",
        side_effect=ProposalReviewError("찾을 수 없다"),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/artifacts/{uuid.uuid4()}/approve"
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"


# ======================= 엔드포인트: 블록 결정·발행 =======================
#
# 여기는 실 UnitOfWork로 돈다. 블록 결정은 저널 유일 제약 위의 upsert이고
# 발행은 그 저널을 모아 판을 쌓는 일이라, 대역으로 바꾸면 정작 확인하려는
# 부분 승인이 DB에서 성립하는지를 볼 수 없다.


def _seed_two_block_proposal(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    admin_user_id: int | None = None,
) -> tuple[uuid.UUID, tuple[ArtifactBlock, ...]]:
    """블록 두 칸짜리 계류 변경안을 실 DB로 심는다."""
    node_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            KnowledgeNode(
                id=node_id,
                workspace_id=workspace_id,
                node_kind="entity",
                entity_type="feature",
                canonical_key=f"test:block-review:{uuid.uuid4().hex}",
                display_name="속도 제한 기능",
            )
        )
        session.commit()

    blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="rate_limit",
            body="rate_limit은 60이다",
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="1",
        ),
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="owner",
            body="담당은 플랫폼 팀이다",
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="1",
        ),
    )
    content_hash = blocks_content_hash(blocks)
    definition_id, channel_id = _seed_definition(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=admin_user_id,
    )
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        artifact_id = uow.artifacts.get_or_create_definition_artifact(
            definition_id=definition_id,
            channel_id=channel_id,
            kind="entity_summary",
            subject_node_id=node_id,
            title="오픈 API",
        )
        proposal_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=blocks,
            content_hash=content_hash,
            idempotency_key=artifact_idempotency_key(
                artifact_id, content_hash, base_revision_id=None
            ),
            base_revision_id=None,
        )
        uow.commit()
    return proposal_id, blocks


def _verdict_path(proposal_id: uuid.UUID, block_index: int) -> str:
    """블록 결정 엔드포인트 경로를 만든다."""
    return (
        f"/api/v1/knowledge-review/queue/{proposal_id}"
        f"/blocks/{block_index}/verdict"
    )


def test_block_verdict_records_and_absorbs_redecision(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """블록 결정은 저장한 그대로 나오고, 다시 누르면 갱신으로 흡수된다."""
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        first = client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "approved",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )
        second = client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "rejected",
                "rejection_reason": "근거가 부족하다",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )

    assert first.status_code == 200
    body = first.json()
    assert body["proposal_id"] == str(proposal_id)
    assert body["block_index"] == 0
    assert body["verdict"] == "approved"
    assert body["reviewer"] == f"user:{reviewer.id}"
    assert body["chosen_winner_claim_id"] is None

    assert second.status_code == 200
    assert second.json()["verdict"] == "rejected"
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        stored = uow.block_verdicts.list_for_proposal(
            proposal_id=proposal_id
        )
    assert len(stored) == 1
    assert stored[0].verdict == "rejected"
    assert stored[0].rejection_reason == "근거가 부족하다"


def test_block_verdict_stale_hash_returns_409(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """검토자가 본 본문의 지문이 다르면 409 STALE_BLOCK이다."""
    workspace_id, _ = workspace_ids
    proposal_id, _ = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        response = client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "approved",
                "block_content_hash": "0" * 64,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "STALE_BLOCK"


def test_block_verdict_rejection_without_reason_is_422(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """사유 없는 블록 반려는 422 INVALID다.

    500으로 새면 소비자는 자기 입력이 틀렸다는 것을 알 수 없다.
    """
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        response = client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "rejected",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID"


def test_block_verdict_missing_proposal_returns_404(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
) -> None:
    """이 workspace에 없는 변경안의 블록 결정은 404다."""
    with _real_session_local(session_factory):
        response = client.put(
            _verdict_path(uuid.uuid4(), 0),
            json={
                "verdict": "approved",
                "block_content_hash": "0" * 64,
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"


def test_block_verdict_audit_records_block_index(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """블록 결정 감사 기록에는 어느 블록을 결정했는지가 남는다."""
    workspace_id, _ = workspace_ids
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )
    stored = StoredBlockVerdict(
        proposal_id=proposal_id,
        block_index=1,
        block_content_hash="a" * 64,
        verdict="approved",
        rejection_reason=None,
        chosen_winner_claim_id=None,
        reviewer=f"user:{reviewer.id}",
        reviewed_at=AT,
    )

    with (
        patch(
            "catchup.server.knowledge_review.api.upsert_block_verdict",
            return_value=stored,
        ) as service,
        patch("catchup.audit.utils.emit_audit_event") as emit,
    ):
        response = client.put(
            _verdict_path(proposal_id, 1),
            json={
                "verdict": "approved",
                "block_content_hash": "a" * 64,
            },
        )

    assert response.status_code == 200
    assert service.call_args.kwargs["block_index"] == 1
    assert service.call_args.kwargs["reviewer"] == f"user:{reviewer.id}"
    recorded = emit.call_args.kwargs
    assert recorded["action"] == KnowledgeReviewAction.BLOCK_VERDICT
    assert recorded["status"] == AuditStatus.SUCCESS
    assert recorded["metadata"].proposal_id == str(proposal_id)
    assert recorded["metadata"].block_index == 1
    assert recorded["metadata"].workspace_id == workspace_id


def test_publish_partial_approval_creates_revision(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """승인된 블록만으로 새 판을 쌓고 반려 블록은 빠진다."""
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "approved",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )
        client.put(
            _verdict_path(proposal_id, 1),
            json={
                "verdict": "rejected",
                "rejection_reason": "담당이 확정되지 않았다",
                "block_content_hash": block_content_hash(blocks[1]),
            },
        )
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "approved"
    assert body["blocks_published"] == 1
    assert body["blocks_rejected"] == 1
    assert body["revision_number"] == 1
    assert body["contradictions_resolved"] == 0

    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        decided = uow.artifacts.get_proposal(proposal_id=proposal_id)
        latest = uow.artifacts.find_latest_revision_id_and_number(
            artifact_id=decided.artifact_id,
        )
    assert decided.status == "approved"
    assert latest == (uuid.UUID(body["revision_id"]), 1)


def test_publish_undecided_blocks_returns_409_with_indexes(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """결정이 빠진 블록이 있으면 409에 그 번호가 실린다."""
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "approved",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "UNDECIDED_BLOCKS"
    assert detail["undecided_block_indexes"] == [1]


def test_publish_needs_no_verdict_for_unchanged_blocks(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """수정 문서는 바뀐 블록만 결정해도 발행이 200으로 통과한다.

    검토 상세는 발행판과 다른 블록만 내려 준다. 화면에 뜨지 않은 블록에
    결정을 요구하면 검토자가 발행할 길이 없으므로, 발행은 그 블록의 결정
    요구를 면제한다.
    """
    workspace_id, _ = workspace_ids
    first_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        for index, block in enumerate(blocks):
            client.put(
                _verdict_path(first_id, index),
                json={
                    "verdict": "approved",
                    "block_content_hash": block_content_hash(block),
                },
            )
        first = client.post(
            f"/api/v1/knowledge-review/queue/{first_id}/publish",
            json={"base_revision_id": None},
        )

    assert first.status_code == 200
    base_revision_id = first.json()["revision_id"]

    changed = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=blocks[1].heading,
        body="담당은 정산 팀이다",
        claim_ids=blocks[1].claim_ids,
        proposal_ids=(),
        ontology_version="1",
    )
    next_blocks = (blocks[0], changed)
    content_hash = blocks_content_hash(next_blocks)
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        artifact_id = uow.artifacts.get_proposal(
            proposal_id=first_id
        ).artifact_id
        second_id = uow.artifacts.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=next_blocks,
            content_hash=content_hash,
            idempotency_key=artifact_idempotency_key(
                artifact_id,
                content_hash,
                base_revision_id=uuid.UUID(base_revision_id),
            ),
            base_revision_id=uuid.UUID(base_revision_id),
        )
        uow.commit()

    with _real_session_local(session_factory):
        client.put(
            _verdict_path(second_id, 1),
            json={
                "verdict": "approved",
                "block_content_hash": block_content_hash(changed),
            },
        )
        response = client.post(
            f"/api/v1/knowledge-review/queue/{second_id}/publish",
            json={"base_revision_id": base_revision_id},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "approved"
    assert body["blocks_published"] == 2
    assert body["blocks_rejected"] == 0
    assert body["revision_number"] == 2


def test_publish_stale_base_returns_409(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """클라이언트가 본 기준 판이 다르면 409 STALE_BASE_REVISION이다."""
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        for index, block in enumerate(blocks):
            client.put(
                _verdict_path(proposal_id, index),
                json={
                    "verdict": "approved",
                    "block_content_hash": block_content_hash(block),
                },
            )
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": str(uuid.uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "STALE_BASE_REVISION"


def test_publish_audit_records_proposal_id(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """발행 감사 기록에는 어느 안건을 확정했는지가 남는다."""
    workspace_id, _ = workspace_ids
    proposal_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )
    result = PublishResult(
        proposal_id=proposal_id,
        verdict="approved",
        revision_id=revision_id,
        revision_number=2,
        blocks_published=3,
        blocks_rejected=1,
        contradictions_resolved=1,
        claims_accepted=4,
    )

    with (
        patch(
            "catchup.server.knowledge_review.api.publish_artifact_proposal",
            return_value=result,
        ) as service,
        patch("catchup.audit.utils.emit_audit_event") as emit,
    ):
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 200
    assert response.json() == {
        "proposal_id": str(proposal_id),
        "verdict": "approved",
        "revision_id": str(revision_id),
        "revision_number": 2,
        "blocks_published": 3,
        "blocks_rejected": 1,
        "contradictions_resolved": 1,
        "claims_accepted": 4,
    }
    assert service.call_args.kwargs["workspace_id"] == workspace_id
    assert service.call_args.kwargs["reviewer"] == f"user:{reviewer.id}"
    recorded = emit.call_args.kwargs
    assert recorded["action"] == KnowledgeReviewAction.PUBLISH
    assert recorded["metadata"].proposal_id == str(proposal_id)


def test_publish_invalid_returns_422(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """조립이 계약을 어긴 발행은 500이 아니라 422다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )

    with patch(
        "catchup.server.knowledge_review.api.publish_artifact_proposal",
        side_effect=PublishError("INVALID", "조립한 본문이 계약을 어겼다"),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID"
    assert "조립한 본문이" not in response.text


def test_publish_passes_undecided_to_the_service(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """body의 일괄 결정 값이 발행 서비스 인자로 그대로 넘어간다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )
    result = PublishResult(
        proposal_id=proposal_id,
        verdict="rejected",
        revision_id=None,
        revision_number=None,
        blocks_published=0,
        blocks_rejected=2,
        contradictions_resolved=0,
        claims_accepted=0,
    )

    with patch(
        "catchup.server.knowledge_review.api.publish_artifact_proposal",
        return_value=result,
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={
                "base_revision_id": None,
                "undecided": "reject",
                "rejection_reason": "이번 판에는 싣지 않는다",
            },
        )

    assert response.status_code == 200
    assert service.call_args.kwargs["undecided"] == "reject"
    assert (
        service.call_args.kwargs["rejection_reason"]
        == "이번 판에는 싣지 않는다"
    )


def test_publish_undecided_reject_without_reason_returns_400(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """사유 없는 일괄 반려는 서비스에 닿기 전에 400 REASON_REQUIRED다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )

    with patch(
        "catchup.server.knowledge_review.api.publish_artifact_proposal"
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None, "undecided": "reject"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "REASON_REQUIRED"
    service.assert_not_called()


def test_publish_undecided_reject_with_blank_reason_returns_400(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """공백뿐인 사유도 사유가 없는 것과 같게 400으로 막는다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        artifacts=_FakeArtifacts(proposal=_proposal(proposal_id=proposal_id))
    )

    with patch(
        "catchup.server.knowledge_review.api.publish_artifact_proposal"
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={
                "base_revision_id": None,
                "undecided": "reject",
                "rejection_reason": "   ",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "REASON_REQUIRED"
    service.assert_not_called()


def test_approve_after_block_verdict_is_blocked_and_publish_works(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """블록 결정이 시작된 뒤의 통짜 승인은 409로 막힌다.

    통짜 승인은 블록 결정을 읽지 않으므로, 그대로 태우면 사람이 반려한
    블록까지 판에 실린다. 사람의 결정을 덮어쓰는 셈이라 막아야 한다.
    막기만 하고 끝나면 안건이 갇히므로, 같은 안건이 발행 경로로는 정상
    확정되는 것까지 함께 본다.
    """
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        recorded = client.put(
            _verdict_path(proposal_id, 1),
            json={
                "verdict": "rejected",
                "rejection_reason": "담당이 확정되지 않았다",
                "block_content_hash": block_content_hash(blocks[1]),
            },
        )
        blocked = client.post(
            f"/api/v1/knowledge-review/artifacts/{proposal_id}/approve"
        )

    assert recorded.status_code == 200
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "BLOCK_REVIEW_IN_PROGRESS"
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        untouched = uow.artifacts.get_proposal(proposal_id=proposal_id)
    assert untouched.status == "pending"

    with _real_session_local(session_factory):
        client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "approved",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )
        published = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert published.status_code == 200
    assert published.json()["blocks_published"] == 1
    assert published.json()["blocks_rejected"] == 1


def test_block_verdict_on_decided_proposal_returns_409(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """이미 확정된 변경안에는 블록 결정을 더 적을 수 없다."""
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        for index, block in enumerate(blocks):
            client.put(
                _verdict_path(proposal_id, index),
                json={
                    "verdict": "approved",
                    "block_content_hash": block_content_hash(block),
                },
            )
        client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )
        response = client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "rejected",
                "rejection_reason": "역시 아니다",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALREADY_DECIDED"


def test_publish_stale_block_returns_409(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
) -> None:
    """결정을 적은 뒤 본문이 바뀌면 발행이 409 STALE_BLOCK으로 멈춘다."""
    workspace_id, _ = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory,
        workspace_id=workspace_id,
        admin_user_id=reviewer.id,
    )

    with _real_session_local(session_factory):
        for index, block in enumerate(blocks):
            client.put(
                _verdict_path(proposal_id, index),
                json={
                    "verdict": "approved",
                    "block_content_hash": block_content_hash(block),
                },
            )

    # 결정을 적은 뒤 본문이 바뀐 상황을 만든다. 재컴파일이 같은 변경안의
    # 본문을 갈아 끼우는 자리를 저장 계층에서 그대로 흉내낸 것이다.
    changed = (
        blocks[0],
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading=blocks[1].heading,
            body="담당은 인프라 팀이다",
            claim_ids=blocks[1].claim_ids,
            proposal_ids=(),
            ontology_version="1",
        ),
    )
    with session_factory() as session:
        session.execute(
            update(KnowledgeArtifactChangeProposal)
            .where(KnowledgeArtifactChangeProposal.id == proposal_id)
            .values(blocks=serialize_blocks(changed))
        )
        session.commit()

    with _real_session_local(session_factory):
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "STALE_BLOCK"


def test_block_verdict_requires_reviewer(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """블록 결정도 검토자만 할 수 있다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="verdict-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.upsert_block_verdict"
    ) as service:
        response = client.put(
            _verdict_path(uuid.uuid4(), 0),
            json={
                "verdict": "approved",
                "block_content_hash": "a" * 64,
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_REVIEWER"
    service.assert_not_called()


def test_publish_requires_reviewer(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """발행도 검토자만 할 수 있다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="publish-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.publish_artifact_proposal"
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/queue/{uuid.uuid4()}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_REVIEWER"
    service.assert_not_called()


def test_block_verdict_hides_other_workspace_proposal(
    app: FastAPI,
    client: TestClient,
    db: Session,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """다른 workspace의 변경안에는 블록 결정을 적을 수 없다.

    404를 받는 것만으로는 부족하다. 결정 저널이 그대로 비어 있는지도
    확인해 아무것도 쓰이지 않았음을 본다.
    """
    first, second = workspace_ids
    proposal_id, blocks = _seed_two_block_proposal(
        session_factory, workspace_id=second
    )
    outsider = _make_user(db, email="ws-verdict@example.com")
    _join(db, user=outsider, workspace_id=first)
    _grant(db, user=outsider, workspace_id=first)
    as_user(outsider)

    with _real_session_local(session_factory):
        response = client.put(
            _verdict_path(proposal_id, 0),
            json={
                "verdict": "approved",
                "block_content_hash": block_content_hash(blocks[0]),
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=second
    ) as uow:
        stored = uow.block_verdicts.list_for_proposal(
            proposal_id=proposal_id
        )
    assert stored == ()


def test_publish_hides_other_workspace_proposal(
    app: FastAPI,
    client: TestClient,
    db: Session,
    session_factory: Callable[[], Session],
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """다른 workspace의 변경안은 발행할 수도 없다."""
    first, second = workspace_ids
    proposal_id, _ = _seed_two_block_proposal(
        session_factory, workspace_id=second
    )
    outsider = _make_user(db, email="ws-publish@example.com")
    _join(db, user=outsider, workspace_id=first)
    _grant(db, user=outsider, workspace_id=first)
    as_user(outsider)

    with _real_session_local(session_factory):
        response = client.post(
            f"/api/v1/knowledge-review/queue/{proposal_id}/publish",
            json={"base_revision_id": None},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=second
    ) as uow:
        untouched = uow.artifacts.get_proposal(proposal_id=proposal_id)
    assert untouched.status == "pending"


def test_block_response_carries_the_narrative() -> None:
    """검수 응답이 블록 산문을 그대로 싣는다.

    검수자는 산문과 인용 원문을 한 화면에서 대조한다. 산문이 응답에서
    빠지면 그 대조가 불가능해진다.
    """
    claim_id = uuid.uuid4()
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="request_status",
        body="검토 중 (2026-08-15 관찰)",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="v3",
        sources=(
            BlockSource(
                claim_id=claim_id,
                statement="상태는 검토 중이다",
                observed_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
                citation_verified=True,
            ),
        ),
        narrative="이 요구는 아직 검토 중이다.",
    )

    response = _to_block(
        block, block_index=0, verdict=None, reason=None
    )

    assert response.narrative == "이 요구는 아직 검토 중이다."
    assert response.sources[0].statement == "상태는 검토 중이다"


def test_block_response_without_narrative_is_none() -> None:
    """산문이 없던 옛 블록도 그대로 읽힌다."""
    claim_id = uuid.uuid4()
    block = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="request_status",
        body="검토 중 (2026-08-15 관찰)",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="v3",
    )

    assert (
        _to_block(
            block, block_index=0, verdict=None, reason=None
        ).narrative
        is None
    )


def _summary_block(narrative: str | None) -> ArtifactBlock:
    """머리말 블록 하나를 만든다."""
    claim_id = uuid.uuid4()
    return ArtifactBlock(
        block_kind=BLOCK_KIND_SUMMARY,
        heading="one_line_summary",
        body="요청 3건 (2026-08-15 관찰)",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="v3",
        narrative=narrative,
    )


def test_summary_block_response_has_no_derived_sections_field() -> None:
    """머리말 블록이 곧 섹션이므로 파생 필드를 싣지 않는다."""
    response = _to_block(
        _summary_block("A사가 CSV 내보내기를 원한다."),
        block_index=0,
        verdict=None,
        reason=None,
    )

    assert response.narrative == "A사가 CSV 내보내기를 원한다."
    assert "summary_sections" not in response.model_dump()


def test_base_summary_block_response_has_no_derived_sections_field() -> None:
    """발행판 블록도 파생 필드 없이 산문만 싣는다."""
    response = _to_base_block(
        _summary_block("A사가 CSV 내보내기를 원한다."), block_index=0
    )

    assert response.narrative == "A사가 CSV 내보내기를 원한다."
    assert "summary_sections" not in response.model_dump()

