from __future__ import annotations

import pytest

from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    IdentityGroupOutput,
)
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    IdentityPartitionOutput,
)
from catchup.knowledge_maintenance.domain.entity_blocking import BlockingMember
from catchup.knowledge_maintenance.domain.entity_blocking import BlockingOrigin
from catchup.knowledge_maintenance.domain.entity_blocking import EntityBlock
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityGroup
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityPartition
from catchup.knowledge_maintenance.domain.entity_resolution import (
    PartitionContractError,
)
from catchup.knowledge_maintenance.domain.entity_resolution import validate_partition


def _group(name: str, member_ids: tuple[str, ...]) -> IdentityGroup:
    return IdentityGroup(
        canonical_name=name,
        canonical_type="feature_request",
        member_ids=member_ids,
        reason="같은 연동 기능을 가리킨다",
    )


def test_full_cover_without_overlap_passes() -> None:
    """전원이 정확히 한 번씩 배정되면 통과한다."""
    partition = IdentityPartition(
        groups=(
            _group("Google Workspace 연동", ("a", "b")),
            _group("결제 실패 알림", ("c",)),
        )
    )

    validate_partition(
        partition, ("a", "b", "c"), entity_type="feature_request"
    )


def test_unassigned_member_raises() -> None:
    """빠진 멤버가 있으면 예외다. 조용히 버리면 후보가 사라진다."""
    partition = IdentityPartition(groups=(_group("가", ("a", "b")),))

    with pytest.raises(PartitionContractError):
        validate_partition(
        partition, ("a", "b", "c"), entity_type="feature_request"
    )


def test_duplicate_assignment_raises() -> None:
    """한 멤버가 두 그룹에 들어가면 예외다."""
    partition = IdentityPartition(
        groups=(_group("가", ("a", "b")), _group("나", ("b", "c")))
    )

    with pytest.raises(PartitionContractError):
        validate_partition(
        partition, ("a", "b", "c"), entity_type="feature_request"
    )


def test_unknown_member_raises() -> None:
    """블록에 없던 멤버가 나오면 예외다."""
    partition = IdentityPartition(groups=(_group("가", ("a", "b", "z")),))

    with pytest.raises(PartitionContractError):
        validate_partition(
            partition, ("a", "b"), entity_type="feature_request"
        )


def test_group_type_other_than_block_type_raises() -> None:
    """그룹 종류가 블록 종류와 다르면 예외다.

    블록이 이미 종류를 정해 두었으므로 판정이 종류를 바꿀 자리가 없다.
    """
    partition = IdentityPartition(groups=(_group("가", ("a", "b")),))

    with pytest.raises(PartitionContractError):
        validate_partition(partition, ("a", "b"), entity_type="faq_question")


def test_group_needs_at_least_one_member() -> None:
    """멤버가 없는 그룹은 만들 수 없다."""
    with pytest.raises(ValueError):
        _group("가", ())


def test_partition_needs_at_least_one_group() -> None:
    """그룹이 없는 분할은 만들 수 없다."""
    with pytest.raises(ValueError):
        IdentityPartition(groups=())


class _FakeStructured:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def ainvoke(self, rendered: str) -> dict:
        self.prompts.append(rendered)
        return self.response


class _FakeLlm:
    """스키마별로 다른 구조화 출력을 돌려주는 가짜 모델이다."""

    def __init__(self, partition_response: dict) -> None:
        self.partition_structured = _FakeStructured(partition_response)
        self.other_structured = _FakeStructured({"parsed": None})

    def with_structured_output(self, schema, *args, **kwargs):
        del args, kwargs
        if schema is IdentityPartitionOutput:
            return self.partition_structured
        return self.other_structured


def _block() -> EntityBlock:
    return EntityBlock(
        entity_type="feature_request",
        members=(
            BlockingMember(
                member_id="a",
                entity_type="feature_request",
                name="Google Workspace 연동",
                origin=BlockingOrigin.CANDIDATE,
                excerpt="구글 워크스페이스 연동이 필요합니다.",
            ),
            BlockingMember(
                member_id="b",
                entity_type="feature_request",
                name="Google Workspace 커넥터",
                origin=BlockingOrigin.NODE,
            ),
        ),
    )


def test_partition_output_becomes_domain_partition() -> None:
    """구조화 출력이 IdentityPartition으로 바뀐다."""
    llm = _FakeLlm(
        {
            "parsed": IdentityPartitionOutput(
                groups=[
                    IdentityGroupOutput(
                        canonical_name="Google Workspace 연동",
                        canonical_type="feature_request",
                        member_ids=["a", "b"],
                        reason="둘 다 같은 연동 기능이다",
                    )
                ]
            ),
            "raw": None,
        }
    )
    judge = BedrockIdentityJudge(llm)

    partition = judge.partition(_block())

    assert len(partition.groups) == 1
    assert partition.groups[0].member_ids == ("a", "b")
    rendered = llm.partition_structured.prompts[0]
    assert "Google Workspace 커넥터" in rendered
    assert "구글 워크스페이스 연동이 필요합니다." in rendered


def test_partition_contract_violation_raises() -> None:
    """전원 배정을 어긴 출력은 블록 격리 예외로 올린다."""
    llm = _FakeLlm(
        {
            "parsed": IdentityPartitionOutput(
                groups=[
                    IdentityGroupOutput(
                        canonical_name="Google Workspace 연동",
                        canonical_type="feature_request",
                        member_ids=["a"],
                        reason="하나만 골랐다",
                    )
                ]
            ),
            "raw": None,
        }
    )
    judge = BedrockIdentityJudge(llm)

    with pytest.raises(PartitionContractError):
        judge.partition(_block())


def test_partition_parse_failure_raises() -> None:
    """계약을 만족하지 못한 출력은 예외다. 블록 skip은 서비스의 몫이다."""
    llm = _FakeLlm({"parsed": None, "parsing_error": "invalid json"})
    judge = BedrockIdentityJudge(llm)

    with pytest.raises(PartitionContractError):
        judge.partition(_block())
