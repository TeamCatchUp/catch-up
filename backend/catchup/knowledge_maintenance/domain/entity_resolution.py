from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

# 시스템이 스스로 승인했을 때 결정 저널에 남기는 검토자 이름의 앞머리다.
# 사람 검토자 이름과 이 앞머리가 겹치지 않아야 "누가 정했나"를 값 하나로
# 가를 수 있다. 계약은 앞머리이므로 읽는 쪽은 특정 이름이 아니라 이 값으로
# 판별하고, 쓰는 쪽은 이 값에서 제 이름을 만든다.
SYSTEM_REVIEWER_PREFIX = "system:"

# 자동 병합이 스스로 승인할 때 쓰는 검토자 이름이다.
SYSTEM_AUTO_MERGE_REVIEWER = f"{SYSTEM_REVIEWER_PREFIX}auto_merge"


@dataclass(frozen=True, slots=True)
class MergeGroup:
    """같은 정규화 이름으로 묶인 pending 후보들을 표현한다."""

    normalized_name: str
    candidate_ids: tuple[uuid.UUID, ...]

    def __post_init__(self) -> None:
        if not self.normalized_name.strip():
            raise ValueError("normalized_name must not be blank")
        if len(self.candidate_ids) < 2:
            raise ValueError("merge group needs at least two candidates")


@dataclass(frozen=True, slots=True)
class IdentityVerdict:
    """같은 이름 그룹이 같은 대상인지에 대한 판정을 표현한다.

    same이면 canonical entity_type과 display_name 제안이 함께 있어야
    한다. 제안 없이 합치라는 판정은 적용할 수 없다.

    model_id와 prompt_version은 이 판정을 누가 어떤 문장으로 냈는지를
    적는 자리다. 판정 결과를 되짚을 때 모델과 프롬프트가 그 사이에 바뀌었는지
    알아야 하므로, 판정을 낸 어댑터가 채워서 넘긴다. 판정기가 LLM이 아니면
    비어 있을 수 있다.

    Attributes:
        same: 그룹이 같은 대상인지 나타낸다.
        reason: 판정의 근거 한 문장을 담는다.
        proposed_type: same일 때 제안하는 entity 종류를 담는다.
        proposed_name: same일 때 제안하는 표시 이름을 담는다.
        model_id: 판정을 낸 모델 식별자를 담는다.
        prompt_version: 판정에 쓴 프롬프트 판본을 담는다.
    """

    same: bool
    reason: str
    proposed_type: str | None = None
    proposed_name: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if self.same and not (
            (self.proposed_type or "").strip()
            and (self.proposed_name or "").strip()
        ):
            raise ValueError(
                "same verdict must propose canonical type and name"
            )


class PartitionContractError(ValueError):
    """분할 판정이 계약을 어겼음을 알린다.

    호출자는 이 예외를 그 블록 하나를 이번 라운드에서 접는 신호로 읽는다.
    배정이 어긋난 분할을 그대로 쓰면 후보가 조용히 사라지거나 한 후보가 두
    노드에 걸리므로, 블록만 격리하고 나머지 블록은 계속 간다.
    """


@dataclass(frozen=True, slots=True)
class IdentityGroup:
    """블록 안에서 같은 대상으로 묶인 멤버들을 표현한다.

    Attributes:
        canonical_name: 이 정체의 대표 표시 이름을 담는다.
        canonical_type: 이 정체의 entity 종류를 담는다.
        member_ids: 이 정체에 속한 멤버 식별자들을 담는다.
        reason: 묶은 근거 한 문장을 담는다.
    """

    canonical_name: str
    canonical_type: str
    member_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.canonical_name.strip():
            raise ValueError("canonical_name must not be blank")
        if not self.canonical_type.strip():
            raise ValueError("canonical_type must not be blank")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if not self.member_ids:
            raise ValueError("identity group needs at least one member")


@dataclass(frozen=True, slots=True)
class IdentityPartition:
    """블록 하나를 정체 여러 개로 가른 결과를 표현한다.

    쌍 단위 판정과 달리 블록 전체를 한 번에 가른다. 쌍으로 물으면 호출
    수가 짝의 수만큼 늘고, A와 B는 같고 B와 C도 같은데 A와 C는 다르다는
    답이 와도 조정할 자리가 없기 때문이다.

    model_id와 prompt_version은 이 분할을 누가 어떤 문장으로 냈는지를
    적는 자리다. 판정을 낸 어댑터가 채워서 넘기고, 병합 제안이 그 값을
    판정 근거에 실어 event 저널까지 옮긴다. 판정기가 LLM이 아니면 비어
    있을 수 있다.

    Attributes:
        groups: 블록을 가른 정체들을 담는다.
        model_id: 분할을 낸 모델 식별자를 담는다.
        prompt_version: 분할에 쓴 프롬프트 판본을 담는다.
    """

    groups: tuple[IdentityGroup, ...]
    model_id: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not self.groups:
            raise ValueError("partition needs at least one group")


def validate_partition(
    partition: IdentityPartition,
    member_ids: Sequence[str],
    *,
    entity_type: str,
) -> None:
    """분할이 블록 멤버를 정확히 한 번씩 덮고 종류를 지키는지 본다.

    넷을 본다. 블록에 없던 멤버가 나왔는지, 두 그룹에 걸친 멤버가 있는지,
    어느 그룹에도 못 들어간 멤버가 있는지, 그룹의 canonical_type이 블록의
    entity_type과 다른지다. 모델 출력은 이 넷을 모두 어길 수 있고, 어긴
    채로 뒤 단계에 넘기면 후보가 사라지거나 한 후보가 두 노드에 붙는다.

    종류를 함께 보는 이유는 블록이 이미 entity_type 단위로 묶여 있어
    종류가 정해져 있기 때문이다. 판정은 누가 누구와 같은 대상인지만
    정하면 된다. 모델이 종류까지 바꾸면 그 값이 그대로 proposal의
    proposed_type이 되고, 자동 병합에서는 사람이 보기 전에 잘못된 종류의
    노드가 선다.

    Raises:
        PartitionContractError: 넷 중 하나라도 어겼을 때 던진다.
    """
    expected = set(member_ids)
    seen: set[str] = set()
    for group in partition.groups:
        if group.canonical_type != entity_type:
            raise PartitionContractError(
                "그룹의 entity 종류가 블록과 다르다: "
                f"{group.canonical_type} (블록 {entity_type})"
            )
        for member_id in group.member_ids:
            if member_id not in expected:
                raise PartitionContractError(
                    f"블록에 없는 멤버가 배정되었다: {member_id}"
                )
            if member_id in seen:
                raise PartitionContractError(
                    f"한 멤버가 두 그룹에 배정되었다: {member_id}"
                )
            seen.add(member_id)

    missing = expected - seen
    if missing:
        raise PartitionContractError(
            f"배정되지 않은 멤버가 있다: {sorted(missing)}"
        )


def normalize_name(name: str) -> str:
    """표기 차이를 접어 이름 비교의 기준을 만든다.

    NFKC 정규화, 공백 접기, casefold까지만 한다. 조사나 접미사는
    건드리지 않는다 — 키를 좁게 잡아 과병합을 피하는 원칙 그대로다.
    """
    collapsed = " ".join(unicodedata.normalize("NFKC", name).split())
    return collapsed.casefold()


def anchor_excerpt(content: str, name: str, *, window: int = 300) -> str:
    """이름의 첫 언급 주변으로 발췌 창을 맞춘다.

    entity evidence는 문서 단위라 인용 span이 없다. 문서 앞부분을
    그대로 자르면 후보가 뒤에서 언급될 때 엉뚱한 맥락이 판정에
    들어가므로, 이름을 본문에서 찾아 그 주변을 뜬다. 이름이 없으면
    (추출기가 표기를 바꾼 경우) 문서 앞부분으로 물러난다.
    """
    if len(content) <= window:
        return content

    position = content.find(name)
    if position < 0:
        position = content.casefold().find(name.casefold())
    if position < 0:
        return content[:window]

    start = max(0, position - (window - len(name)) // 2)
    start = min(start, len(content) - window)
    return content[start : start + window]


def deterministic_canonical_key(
    source_type: str,
    entity_type: str,
    external_key: str,
) -> str:
    """외부 ID 기반의 틀릴 수 없는 canonical key를 만든다."""
    return f"{source_type}:{entity_type}:{external_key}"
