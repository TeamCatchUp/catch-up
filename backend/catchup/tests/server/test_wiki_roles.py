"""역할 판정 순수 로직을 검증한다. DB 없이 dataclass만으로 돈다."""

import uuid

from catchup.server.wiki.roles import WikiRoleContext
from catchup.server.wiki.roles import can_decide_artifact
from catchup.server.wiki.roles import can_manage_owners


def _roles(**kwargs) -> WikiRoleContext:
    """판정에 넣을 역할 스냅샷 하나를 만든다."""
    base = dict(
        is_global_admin=False,
        admin_channel_ids=frozenset(),
        owned_artifact_ids=frozenset(),
    )
    base.update(kwargs)
    return WikiRoleContext(**base)


def test_owner_decides_own_artifact() -> None:
    """담당자는 자기 문서를 결정한다."""
    artifact_id = uuid.uuid4()
    roles = _roles(owned_artifact_ids=frozenset({artifact_id}))
    assert can_decide_artifact(
        roles,
        artifact_channel_id=uuid.uuid4(),
        artifact_id=artifact_id,
        owner_user_ids=frozenset({7}),
        user_id=7,
    )


def test_admin_fallback_only_when_no_owner() -> None:
    """관리자는 담당자 없는 문서에서만 폴백으로 선다."""
    channel_id = uuid.uuid4()
    roles = _roles(admin_channel_ids=frozenset({channel_id}))
    common = dict(
        artifact_channel_id=channel_id,
        artifact_id=uuid.uuid4(),
        user_id=7,
    )
    assert can_decide_artifact(roles, owner_user_ids=frozenset(), **common)
    # 담당자가 있으면 관리자라도 못 만진다 — 매트릭스의 "폴백 항목만".
    assert not can_decide_artifact(
        roles, owner_user_ids=frozenset({99}), **common
    )


def test_global_admin_fallback_for_unassigned_artifact() -> None:
    """미분류 문서의 폴백은 전역 ADMIN이다."""
    roles = _roles(is_global_admin=True)
    assert can_decide_artifact(
        roles,
        artifact_channel_id=None,
        artifact_id=uuid.uuid4(),
        owner_user_ids=frozenset(),
        user_id=7,
    )
    # 담당자가 생기면 전역 ADMIN이라도 못 만진다.
    assert not can_decide_artifact(
        roles,
        artifact_channel_id=None,
        artifact_id=uuid.uuid4(),
        owner_user_ids=frozenset({99}),
        user_id=7,
    )


def test_member_without_roles_decides_artifact_without_owner() -> None:
    """역할이 없는 구성원도 담당자 없는 문서는 결정한다.

    채널에 놓인 문서든 미분류 문서든 같다. 담당자가 아무도 없으면 결정할
    사람이 한 명도 없어 문서가 멈추기 때문에, 구성원 폴백이 마지막 단계로
    선다.
    """
    assert can_decide_artifact(
        _roles(),
        artifact_channel_id=None,
        artifact_id=uuid.uuid4(),
        owner_user_ids=frozenset(),
        user_id=7,
    )
    assert can_decide_artifact(
        _roles(),
        artifact_channel_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        owner_user_ids=frozenset(),
        user_id=7,
    )


def test_member_without_roles_cannot_decide_owned_artifact() -> None:
    """담당자가 있는 문서에는 구성원 폴백이 서지 않는다."""
    assert not can_decide_artifact(
        _roles(),
        artifact_channel_id=None,
        artifact_id=uuid.uuid4(),
        owner_user_ids=frozenset({99}),
        user_id=7,
    )


def test_owner_row_without_role_snapshot_is_not_enough() -> None:
    """담당자 명단에 있어도 이 사용자의 역할 스냅샷에 없으면 막는다.

    두 조건을 함께 요구하는 이유는 스냅샷이 남의 workspace 문서까지 담을 수
    있기 때문이다. 대상 문서 id 일치와 명단 포함이 둘 다 성립해야 담당자다.
    """
    artifact_id = uuid.uuid4()
    assert not can_decide_artifact(
        _roles(),
        artifact_channel_id=None,
        artifact_id=artifact_id,
        owner_user_ids=frozenset({7}),
        user_id=7,
    )


def test_owner_assigns_but_admin_is_not_blocked_by_owners() -> None:
    """지정은 담당자 본인도, 그 채널 관리자도 할 수 있다.

    검수와 갈리는 지점이다. 검수에서 관리자는 담당자 없는 문서의 폴백이지만,
    지정은 확정 매트릭스가 "관리자 ○ 모든 문서"라 담당자가 있어도 선다.
    """
    channel_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    owner_user_ids = frozenset({7})
    common = dict(
        artifact_channel_id=channel_id,
        artifact_id=artifact_id,
        owner_user_ids=owner_user_ids,
        for_removal=False,
    )

    owner = _roles(owned_artifact_ids=frozenset({artifact_id}))
    assert can_manage_owners(owner, user_id=7, **common)

    admin = _roles(admin_channel_ids=frozenset({channel_id}))
    assert can_manage_owners(admin, user_id=9, **common)


def test_stranger_cannot_assign_owner() -> None:
    """역할이 없는 구성원도, 남의 채널 관리자도 지정하지 못한다."""
    artifact_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    common = dict(
        artifact_channel_id=channel_id,
        artifact_id=artifact_id,
        owner_user_ids=frozenset(),
        user_id=7,
        for_removal=False,
    )

    assert not can_manage_owners(_roles(), **common)
    # 다른 채널의 관리자는 이 문서에 서지 못한다.
    assert not can_manage_owners(
        _roles(admin_channel_ids=frozenset({uuid.uuid4()})), **common
    )
    # 채널 문서는 전역 ADMIN이라도 그 채널 관리자가 아니면 불가다.
    assert not can_manage_owners(_roles(is_global_admin=True), **common)


def test_owner_cannot_remove_owner() -> None:
    """해제는 관리자만이다 — 담당자 본인도 막힌다."""
    channel_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    common = dict(
        artifact_channel_id=channel_id,
        artifact_id=artifact_id,
        owner_user_ids=frozenset({7}),
        user_id=7,
        for_removal=True,
    )

    assert not can_manage_owners(
        _roles(owned_artifact_ids=frozenset({artifact_id})), **common
    )
    assert can_manage_owners(
        _roles(admin_channel_ids=frozenset({channel_id})), **common
    )


def test_unassigned_artifact_owner_removal_needs_global_admin() -> None:
    """미분류 문서의 해제 폴백은 전역 ADMIN 하나다."""
    artifact_id = uuid.uuid4()
    common = dict(
        artifact_channel_id=None,
        artifact_id=artifact_id,
        owner_user_ids=frozenset({7}),
        user_id=7,
        for_removal=True,
    )

    assert can_manage_owners(_roles(is_global_admin=True), **common)
    # 어느 채널의 관리자든 미분류 문서에는 서지 못한다.
    assert not can_manage_owners(
        _roles(admin_channel_ids=frozenset({uuid.uuid4()})), **common
    )


def test_has_any_role_reflects_each_source() -> None:
    """어느 역할 하나만 있어도 검수 표면에 설 자격이 생긴다."""
    assert not _roles().has_any_role
    assert _roles(is_global_admin=True).has_any_role
    assert _roles(admin_channel_ids=frozenset({uuid.uuid4()})).has_any_role
    assert _roles(owned_artifact_ids=frozenset({uuid.uuid4()})).has_any_role
