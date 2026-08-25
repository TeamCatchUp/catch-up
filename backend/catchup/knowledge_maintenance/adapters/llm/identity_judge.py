from __future__ import annotations

import asyncio
import time

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from pydantic import ConfigDict

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.domain.entity_blocking import EntityBlock
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityGroup
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityPartition
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict
from catchup.knowledge_maintenance.domain.entity_resolution import (
    PartitionContractError,
)
from catchup.knowledge_maintenance.domain.entity_resolution import validate_partition
from catchup.knowledge_maintenance.ports.identity_judge import JudgeCandidate
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/judge_entity_identity.j2"
PARTITION_TEMPLATE_PATH = "knowledge_maintenance/partition_entity_block.j2"
JUDGE_PROMPT_VERSION = versioned_prompt(TEMPLATE_PATH)
PARTITION_PROMPT_VERSION = versioned_prompt(PARTITION_TEMPLATE_PATH)

logger = get_logger(__name__)


def _read_model_id(llm: object) -> str | None:
    """판정에 쓰는 모델의 식별자를 찾는다.

    제공자마다 식별자를 들고 있는 속성 이름이 달라 `model_id`와 `model`을
    차례로 본다. 어느 쪽에도 쓸 만한 값이 없으면 None을 준다. 식별자를
    못 찾았다고 판정을 멈출 이유는 없고, 판정 근거에서 그 키만 빠진다.
    """
    for attribute in ("model_id", "model"):
        value = getattr(llm, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class IdentityJudgeOutput(BaseModel):
    """판정 LLM의 구조화 출력 계약을 정의한다.

    Attributes:
        same: 그룹이 같은 대상인지 나타낸다.
        reason: 판정의 근거 한 문장을 담는다.
        canonical_type: same일 때 제안하는 entity 종류를 나타낸다.
        canonical_name: same일 때 제안하는 표시 이름을 나타낸다.
    """

    model_config = ConfigDict(frozen=True)

    same: bool
    reason: str
    canonical_type: str | None = None
    canonical_name: str | None = None


class IdentityGroupOutput(BaseModel):
    """분할 판정이 내놓는 그룹 하나의 계약을 정의한다.

    Attributes:
        canonical_name: 이 정체의 대표 표시 이름을 나타낸다.
        canonical_type: 이 정체의 entity 종류를 나타낸다.
        member_ids: 이 정체에 속한 멤버 식별자들을 나타낸다.
        reason: 묶은 근거 한 문장을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    canonical_name: str
    canonical_type: str
    member_ids: list[str]
    reason: str


class IdentityPartitionOutput(BaseModel):
    """분할 판정 LLM의 구조화 출력 계약을 정의한다."""

    model_config = ConfigDict(frozen=True)

    groups: list[IdentityGroupOutput]


class BedrockIdentityJudge:
    """엔티티 identity를 LLM으로 판정한다.

    묻는 방식이 둘이다. `judge`는 같은 이름 그룹 하나에 예·아니오를 묻고,
    `partition`은 이름이 서로 다를 수 있는 블록을 정체 여러 개로 갈라
    달라고 묻는다. 프롬프트도 구조화 출력도 서로 다르므로 나눠 둔다.

    port는 sync다. 서비스와 러너가 이벤트 루프를 몰라도 되도록 비동기
    호출을 여기서 감싼다.

    판정 결과에는 쓴 모델 식별자와 프롬프트 판본을 함께 싣는다. 두 값이
    있어야 나중에 판정을 되짚을 때 그 사이에 모델이나 프롬프트가 바뀌었는지
    가릴 수 있다. 로그에만 남기면 event 저널에서는 알 수 없다.

    entity 종류 사전은 생성 시점에 주입한다. anchored 종류는 소속 없이
    이름만으로 지시 대상이 정해지지 않으므로 판정 규칙이 달라진다. 사전이
    비면 프롬프트에서 그 규칙이 통째로 빠진다.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        entity_types: tuple[EntityTypeEntry, ...] = (),
    ) -> None:
        self._entity_types = entity_types
        self._model_id = _read_model_id(llm)
        self._structured = llm.with_structured_output(
            IdentityJudgeOutput,
            method="function_calling",
            include_raw=True,
        )
        self._partition_structured = llm.with_structured_output(
            IdentityPartitionOutput,
            method="function_calling",
            include_raw=True,
        )

    def judge(
        self,
        group: tuple[JudgeCandidate, ...],
    ) -> IdentityVerdict:
        """그룹이 같은 대상인지 판정한다. 계약 위반이면 예외를 올린다."""
        # 사전 정의문은 발췌와 달리 규칙 자리에 그대로 들어간다. 검토를
        # 거쳐 발행된 계약 문장이기 때문이다. 원문에서 흘러든 텍스트를
        # 여기에 넣으면 발췌 격리 문단을 우회하는 통로가 된다.
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            candidates=group,
            entity_types=self._entity_types,
        )

        started = time.perf_counter()
        response = asyncio.run(self._structured.ainvoke(rendered))
        elapsed = round(time.perf_counter() - started, 3)

        parsed = response.get("parsed")
        if parsed is None:
            error = response.get("parsing_error")
            logger.warning(
                "identity_judge_rejected",
                reason="contract_violation",
                detail=str(error) if error is not None else "unknown",
                group_size=len(group),
                elapsed=elapsed,
            )
            raise ValueError(
                f"판정 출력이 계약을 만족하지 않는다: {error}"
            )

        logger.info(
            "identity_judge_completed",
            same=parsed.same,
            group_size=len(group),
            elapsed=elapsed,
        )
        return IdentityVerdict(
            same=parsed.same,
            reason=parsed.reason,
            proposed_type=parsed.canonical_type,
            proposed_name=parsed.canonical_name,
            model_id=self._model_id,
            prompt_version=JUDGE_PROMPT_VERSION,
        )

    def partition(self, block: EntityBlock) -> IdentityPartition:
        """블록 하나를 정체 여러 개로 가른다.

        블록당 호출은 한 번이다. 로그에는 블록 크기와 그룹 수, 프롬프트
        판본만 남긴다. 멤버 이름과 발췌는 남기지 않는다. 원문에서 흘러든
        텍스트이고 감사 로그는 오래 남기 때문이다.

        Raises:
            PartitionContractError: 출력이 계약을 어겼거나, 그룹 하나가
                도메인 규칙을 어겼거나, 배정이 블록 멤버를 정확히 한 번씩
                덮지 않을 때 던진다.
        """
        rendered = prompt_loader.get_prompt(
            PARTITION_TEMPLATE_PATH,
            entity_type=block.entity_type,
            members=block.members,
        )

        started = time.perf_counter()
        response = asyncio.run(self._partition_structured.ainvoke(rendered))
        elapsed = round(time.perf_counter() - started, 3)

        parsed = response.get("parsed")
        if parsed is None:
            error = response.get("parsing_error")
            logger.warning(
                "identity_partition_failed",
                reason="contract_violation",
                error_type=type(error).__name__ if error is not None else "unknown",
                prompt_version=PARTITION_PROMPT_VERSION,
                block_size=len(block.members),
                elapsed=elapsed,
            )
            raise PartitionContractError("분할 출력이 계약을 만족하지 않는다.")

        try:
            partition = IdentityPartition(
                groups=tuple(
                    IdentityGroup(
                        canonical_name=group.canonical_name,
                        canonical_type=group.canonical_type,
                        member_ids=tuple(group.member_ids),
                        reason=group.reason,
                    )
                    for group in parsed.groups
                ),
                model_id=self._model_id,
                prompt_version=PARTITION_PROMPT_VERSION,
            )
        except ValueError as error:
            logger.warning(
                "identity_partition_failed",
                reason="group_rule_violation",
                prompt_version=PARTITION_PROMPT_VERSION,
                block_size=len(block.members),
                elapsed=elapsed,
            )
            raise PartitionContractError(f"분할 그룹이 규칙을 어겼다: {error}") from error

        try:
            validate_partition(
                partition,
                block.member_ids,
                entity_type=block.entity_type,
            )
        except PartitionContractError:
            logger.warning(
                "identity_partition_failed",
                reason="assignment_violation",
                prompt_version=PARTITION_PROMPT_VERSION,
                block_size=len(block.members),
                group_count=len(partition.groups),
                elapsed=elapsed,
            )
            raise

        logger.info(
            "identity_partition_completed",
            prompt_version=PARTITION_PROMPT_VERSION,
            block_size=len(block.members),
            group_count=len(partition.groups),
            elapsed=elapsed,
        )
        return partition
