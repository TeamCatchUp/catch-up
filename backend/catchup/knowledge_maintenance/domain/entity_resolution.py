from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass


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
    """

    same: bool
    reason: str
    proposed_type: str | None = None
    proposed_name: str | None = None

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


def normalize_name(name: str) -> str:
    """표기 차이를 접어 이름 비교의 기준을 만든다.

    NFKC 정규화, 공백 접기, casefold까지만 한다. 조사나 접미사는
    건드리지 않는다 — 키를 좁게 잡아 과병합을 피하는 원칙 그대로다.
    """
    collapsed = " ".join(unicodedata.normalize("NFKC", name).split())
    return collapsed.casefold()


def deterministic_canonical_key(
    source_type: str,
    entity_type: str,
    external_key: str,
) -> str:
    """외부 ID 기반의 틀릴 수 없는 canonical key를 만든다."""
    return f"{source_type}:{entity_type}:{external_key}"
