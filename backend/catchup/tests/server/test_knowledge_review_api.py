"""검수 루프 정식 API의 인가·응답·오류 계약을 확인한다.

권한 판정은 실 PostgreSQL로 본다. 소속(user_workspaces)과 검토자 권한
(wiki_reviewer_grants)이 둘 다 DB 사실이고, 대역으로 흉내내면 조인 조건이
틀려도 드러나지 않기 때문이다. 인증만 dependency_overrides로 우회한다 —
쿠키 JWT를 만드는 일은 이 라우터의 검증 대상이 아니다.

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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db.models import KnowledgeNode
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import UserWorkspace
from catchup.db.models import WikiReviewerGrant
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.services.apply_mutation_proposals import ApplyResult
from catchup.knowledge_maintenance.services.list_review_queue import ReviewQueueItem
from catchup.knowledge_maintenance.services.list_review_queue import ReviewQueuePage
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import ReviewResult
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewResult,
)
from catchup.server.knowledge_review.api import router
from catchup.server.knowledge_review.dependencies import ReviewerContext
from catchup.server.knowledge_review.dependencies import get_review_uow_factory
from catchup.server.knowledge_review.dependencies import get_reviewer_user
from catchup.server.knowledge_review.dependencies import resolve_reviewer_workspace

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

    if not inspect(engine).has_table(WikiReviewerGrant.__tablename__):
        engine.dispose()
        pytest.skip("검토자 권한 테이블이 없다. alembic upgrade head가 필요하다.")

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
    """사용자에게 위키 검토자 권한을 준다."""
    db.add(WikiReviewerGrant(user_id=user.id, workspace_id=workspace_id))
    db.flush()


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
        self, *, proposal_id: uuid.UUID
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
        contested: frozenset[uuid.UUID] = frozenset(),
        pending: tuple[StoredContradictionProposal, ...] = (),
        subject_pending: tuple[StoredPendingProposal, ...] = (),
        statuses: dict[uuid.UUID, str] | None = None,
    ) -> None:
        self._contested = contested
        self._pending = pending
        self._subject_pending = subject_pending
        # 실 저장소처럼 계류 여부와 무관하게 상태를 돌려준다. 계류 목록에
        # 없는 안건도 행 자체는 남아 있기 때문이다.
        self._statuses = dict(statuses or {})
        self.workspace_ids: list[int] = []

    def find_contested_subject_node_ids(
        self, *, workspace_id: int
    ) -> frozenset[uuid.UUID]:
        self.workspace_ids.append(workspace_id)
        return self._contested

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


class _FakeUow:
    """라우터가 쓰는 transaction 경계를 흉내낸다."""

    def __init__(
        self,
        *,
        artifacts: _FakeArtifacts,
        mutation_proposals: _FakeMutations,
    ) -> None:
        self.artifacts = artifacts
        self.mutation_proposals = mutation_proposals

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
) -> Callable[[], _FakeUow]:
    """같은 대역 저장소를 계속 돌려주는 factory를 만든다."""
    resolved_artifacts = artifacts or _FakeArtifacts()
    resolved_mutations = mutations or _FakeMutations()

    def factory() -> _FakeUow:
        return _FakeUow(
            artifacts=resolved_artifacts,
            mutation_proposals=resolved_mutations,
        )

    return factory


def _proposal(
    *,
    proposal_id: uuid.UUID,
    status: str = "pending",
    subject_node_id: uuid.UUID | None = None,
    base_revision_id: uuid.UUID | None = None,
    claim_id: uuid.UUID | None = None,
    sources: tuple[BlockSource, ...] = (),
) -> StoredArtifactProposal:
    """상세 응답에 쓸 변경안 한 건을 만든다.

    sources를 주는 호출자는 claim_id도 같이 줘서 근거 인용이 블록
    claim_ids 안에 들게 한다 — 도메인 검증이 요구하는 부분집합 관계를
    대역에서도 지킨다.
    """
    return StoredArtifactProposal(
        id=proposal_id,
        artifact_id=uuid.uuid4(),
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


# ======================= 앱 fixture =======================


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
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


def test_member_without_grant_is_403(
    db: Session, workspace_ids: tuple[int, int]
) -> None:
    """소속만 있고 검토자 권한이 없으면 막는다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="member@example.com")
    _join(db, user=user, workspace_id=workspace_id)

    with pytest.raises(HTTPException) as excinfo:
        resolve_reviewer_workspace(
            workspace_id=workspace_id, current_user=user, db=db
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "NOT_REVIEWER"


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
        "catchup.server.knowledge_review.dependencies.emit_audit_event"
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
        user=user, workspace_id=workspace_id, reviewer=f"user:{user.id}"
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


def test_queue_requires_reviewer(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """검토자 권한이 없으면 목록도 못 본다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="queue-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)

    response = client.get("/api/v1/knowledge-review/queue")

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
        "artifact": {"id": str(item.artifact_id), "title": "오픈 API"},
        "summary": "속도 제한: rate_limit은 60이다",
        "origin": "compiled",
        "contains_conflict": True,
    }
    assert service.call_args.kwargs == {
        "workspace_id": workspace_id,
        "contains_conflict": True,
        "limit": 1,
        "offset": 2,
    }


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
    """상세는 본문·근거 장부와 이 대상에 걸린 충돌을 함께 싣는다."""
    workspace_id, _ = workspace_ids
    proposal_id = uuid.uuid4()
    subject_node_id = uuid.uuid4()
    stored = _proposal(
        proposal_id=proposal_id, subject_node_id=subject_node_id
    )
    conflict_id = uuid.uuid4()
    other_conflict_id = uuid.uuid4()
    claim_id = uuid.uuid4()
    contradiction = StoredContradictionProposal(
        id=conflict_id,
        predicate="rate_limit",
        subject_key=f"node:{subject_node_id}",
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
    mutations = _FakeMutations(
        contested=frozenset({subject_node_id}),
        pending=(contradiction, other),
        subject_pending=(
            StoredPendingProposal(
                id=conflict_id,
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
    assert data["contains_conflict"] is True
    assert data["blocks"][0]["claim_ids"] == [
        str(stored.blocks[0].claim_ids[0])
    ]
    assert data["read_set"] == {
        "claim_ids": [str(stored.blocks[0].claim_ids[0])],
        "proposal_ids": [],
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


# ======================= workspace 경계 =======================
#
# 여기만 실 UnitOfWork를 쓴다. 경계를 지키는 것은 저장소 질의의 where 절이라,
# 대역으로 바꾸면 그 절이 빠져도 테스트가 통과한다. `SessionLocal`만 테스트
# 연결로 바꿔치기해 `get_review_uow_factory`의 workspace 결정 경로는 실제
# 코드가 그대로 돌게 둔다.


def _seed_pending_proposal(
    session_factory: Callable[[], Session], *, workspace_id: int
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
    with KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    ) as uow:
        artifact_id = uow.artifacts.get_or_create_artifact(
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
    proposal_id = _seed_pending_proposal(session_factory, workspace_id=second)

    insider = _make_user(db, email="ws-insider@example.com")
    _join(db, user=insider, workspace_id=second)
    _grant(db, user=insider, workspace_id=second)
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


# ======================= 엔드포인트: 결정 =======================


def test_approve_records_current_user_as_reviewer(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """승인은 판정자로 지금 로그인한 사용자를 넘긴다."""
    proposal_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
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
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
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


def test_reject_passes_reason(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """반려는 사유를 그대로 서비스에 넘긴다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
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


def test_resolve_passes_winner_and_reviewer(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """모순 판정은 승자와 판정자를 서비스에 넘긴다."""
    workspace_id, _ = workspace_ids
    proposal_id = uuid.uuid4()
    winner = uuid.uuid4()
    loser = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        mutations=_FakeMutations(statuses={proposal_id: "pending"})
    )
    result = ContradictionReviewResult(
        proposal_id=proposal_id,
        winner_claim_id=winner,
        loser_claim_ids=(loser,),
        valid_to=AT,
        valid_to_source="winner_valid_from",
    )

    with patch(
        "catchup.server.knowledge_review.api.review_contradiction_proposal",
        return_value=result,
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/contradictions/{proposal_id}/resolve",
            json={"winner_claim_id": str(winner)},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["winner_claim_id"] == str(winner)
    assert data["loser_claim_ids"] == [str(loser)]
    assert data["valid_to_source"] == "winner_valid_from"
    assert service.call_args.kwargs["winner_claim_id"] == winner
    assert service.call_args.kwargs["reviewer"] == f"user:{reviewer.id}"
    assert service.call_args.kwargs["workspace_id"] == workspace_id


def test_resolve_missing_proposal_returns_404(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """없는 모순 안건은 409가 아니라 404다.

    잘못된 식별자와 낡은 큐는 소비자가 할 일이 다르다. 판정에 닿기 전에
    갈리는지도 함께 본다.
    """
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.review_contradiction_proposal"
    ) as service:
        response = client.post(
            "/api/v1/knowledge-review/contradictions"
            f"/{uuid.uuid4()}/resolve",
            json={"winner_claim_id": str(uuid.uuid4())},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"
    service.assert_not_called()


def test_resolve_already_decided_returns_409(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """이미 결정된 모순 안건은 409 ALREADY_DECIDED다.

    사람의 결정은 되돌릴 수 없으므로 판정 서비스에 닿지 않아야 한다.
    """
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        mutations=_FakeMutations(statuses={proposal_id: "approved"})
    )

    with patch(
        "catchup.server.knowledge_review.api.review_contradiction_proposal"
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/contradictions/{proposal_id}/resolve",
            json={"winner_claim_id": str(uuid.uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "ALREADY_DECIDED",
        "message": "이미 결정된 모순 안건입니다.",
    }
    service.assert_not_called()


def test_resolve_non_pending_returns_409_with_code(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """계류 목록에서 사라진 안건은 409 CONTRADICTION_NOT_PENDING이다.

    사전 조회는 계류라고 봤는데 판정이 실패하는 경우다 — 그 사이에 다른
    판정이 먼저 확정한 경합이다.
    """
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        mutations=_FakeMutations(statuses={proposal_id: "pending"})
    )

    with patch(
        "catchup.server.knowledge_review.api.review_contradiction_proposal",
        side_effect=ContradictionReviewError("찾을 수 없다"),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/contradictions/{proposal_id}/resolve",
            json={"winner_claim_id": str(uuid.uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONTRADICTION_NOT_PENDING"


def test_resolve_unknown_winner_returns_409_with_code(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """안건 밖의 주장을 승자로 지정하면 409 WINNER_NOT_CANDIDATE다."""
    proposal_id = uuid.uuid4()
    pending = StoredContradictionProposal(
        id=proposal_id,
        predicate="rate_limit",
        subject_key="node:x",
        summary="갈렸다",
        values=(
            StoredContradictionValue(
                claim_id=uuid.uuid4(),
                value=60,
                normalized="60",
                statement=None,
                observed_at=None,
            ),
        ),
    )
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory(
        mutations=_FakeMutations(
            pending=(pending,), statuses={proposal_id: "pending"}
        )
    )

    with patch(
        "catchup.server.knowledge_review.api.review_contradiction_proposal",
        side_effect=ContradictionReviewError("값 후보가 아니다"),
    ):
        response = client.post(
            f"/api/v1/knowledge-review/contradictions/{proposal_id}/resolve",
            json={"winner_claim_id": str(uuid.uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "WINNER_NOT_CANDIDATE"


# ======================= 엔드포인트: 적용 =======================


def test_apply_all_returns_counts(
    app: FastAPI,
    client: TestClient,
    reviewer: User,
    workspace_ids: tuple[int, int],
) -> None:
    """전체 적용은 집계를 그대로 돌려준다."""
    workspace_id, _ = workspace_ids
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
    result = ApplyResult(
        proposals_applied=2,
        proposals_failed=1,
        candidates_resolved=3,
        candidates_already_resolved=0,
        claims_superseded=4,
        claims_invalidated=0,
        claims_already_closed=1,
    )

    with patch(
        "catchup.server.knowledge_review.api.apply_mutation_proposals",
        return_value=result,
    ) as service:
        response = client.post("/api/v1/knowledge-review/apply")

    assert response.status_code == 200
    assert response.json() == {
        "proposals_applied": 2,
        "proposals_failed": 1,
        "candidates_resolved": 3,
        "candidates_already_resolved": 0,
        "claims_superseded": 4,
        "claims_invalidated": 0,
        "claims_already_closed": 1,
    }
    assert service.call_args.kwargs == {"workspace_id": workspace_id}


def test_apply_single_passes_proposal_id(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """한 건 적용은 안건 식별자를 서비스에 넘긴다."""
    proposal_id = uuid.uuid4()
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
    result = ApplyResult(
        proposals_applied=1,
        proposals_failed=0,
        candidates_resolved=1,
        candidates_already_resolved=0,
    )

    with patch(
        "catchup.server.knowledge_review.api.apply_mutation_proposals",
        return_value=result,
    ) as service:
        response = client.post(
            f"/api/v1/knowledge-review/apply/{proposal_id}"
        )

    assert response.status_code == 200
    assert response.json()["proposals_applied"] == 1
    assert service.call_args.kwargs["proposal_id"] == proposal_id


def test_apply_single_not_found_returns_404(
    app: FastAPI, client: TestClient, reviewer: User
) -> None:
    """적용된 것이 하나도 없으면 404다."""
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()
    result = ApplyResult(
        proposals_applied=0,
        proposals_failed=0,
        candidates_resolved=0,
        candidates_already_resolved=0,
    )

    with patch(
        "catchup.server.knowledge_review.api.apply_mutation_proposals",
        return_value=result,
    ):
        response = client.post(
            f"/api/v1/knowledge-review/apply/{uuid.uuid4()}"
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROPOSAL_NOT_APPLIED"


def test_apply_requires_reviewer(
    app: FastAPI,
    client: TestClient,
    db: Session,
    workspace_ids: tuple[int, int],
    as_user: Callable[[User], None],
) -> None:
    """적용도 검토자만 할 수 있다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="apply-member@example.com")
    _join(db, user=user, workspace_id=workspace_id)
    as_user(user)
    app.dependency_overrides[get_review_uow_factory] = lambda: _fake_factory()

    with patch(
        "catchup.server.knowledge_review.api.apply_mutation_proposals"
    ) as service:
        response = client.post("/api/v1/knowledge-review/apply")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_REVIEWER"
    service.assert_not_called()
