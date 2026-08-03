from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

# YYYY, YYYY-MM, YYYY-MM-DD 접두 형태만 날짜로 인정한다.
_DATE_PREFIX = re.compile(r"\d{4}(-\d{2}){0,2}")


@dataclass(frozen=True, slots=True)
class StoredClaimCandidate:
    """저장된 claim 후보를 모순 판정이 읽는 형태로 표현한다.

    subject는 같은 run에서 나온 entity 후보이거나 이미 존재하는 canonical
    node다. 둘 중 정확히 하나만 값을 갖는다. entity 후보가 subject라면 그
    후보가 어느 노드로 해소됐는지를 `subject_resolved_node_id`가 알려준다.
    같은 대상에 대한 주장인지를 후보 식별자가 아니라 해소 결과로 묶어야
    하기 때문이다.

    Attributes:
        id: claim 후보 행을 식별한다.
        subject_entity_candidate_id: subject가 된 entity 후보를 가리킨다.
        subject_node_id: subject가 된 canonical 노드를 가리킨다.
        subject_resolved_node_id: subject 후보의 해소 결과를 가리킨다.
        predicate: 어떤 속성에 대한 주장인지 나타낸다.
        value_type: 값의 종류를 나타낸다.
        value: 주장된 값을 보존한다.
        statement: 주장을 사람이 읽는 문장으로 보존한다.
        observed_at: 주장이 나온 원문을 관찰한 시각을 나타낸다.
        valid_to: 주장이 참이었던 구간의 끝을 나타낸다. 아직 참이면
            None이다. 닫힌 주장은 더 이상 모순의 당사자가 아니고
            문서의 현재 판에도 실리지 않는다.
        citation_verified: 근거 인용의 원문 대조 결과를 나타낸다. True는
            locator가 확정된 검증 인용, False는 evidence는 있으나 대조에
            실패한 환각 의심, None은 evidence link가 없는 경우다.
    """

    id: uuid.UUID
    subject_entity_candidate_id: uuid.UUID | None
    subject_node_id: uuid.UUID | None
    subject_resolved_node_id: uuid.UUID | None
    predicate: str
    value_type: str
    value: object
    statement: str
    observed_at: datetime
    valid_to: datetime | None = None
    citation_verified: bool | None = None


def normalize_value(
    value_type: str,
    value: object,
    *,
    enum_values: tuple[str, ...] = (),
) -> str | None:
    """value_type 규칙으로 비교 키를 만든다. 실패하면 None이다.

    enum은 사전이 준 enum_values 안의 값만 비교 키가 된다. 사전 밖
    값을 통과시키면 extractor 신조어가 검토된 치역인 척 모순 비교에
    섞인다. enum_values가 비어 있으면 대조 없이 통과한다 — 치역을
    모르는 호출자가 값을 잃지 않게 하기 위해서다.
    """
    if value_type == "number":
        try:
            return repr(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    if value_type == "boolean":
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str) and value.strip().lower() in (
            "true",
            "false",
        ):
            return value.strip().lower()
        return None
    if value_type == "date":
        if isinstance(value, str):
            text = value.strip()
            if _DATE_PREFIX.fullmatch(text):
                return text
        return None
    if value_type == "enum":
        if not isinstance(value, str) or not value.strip():
            return None
        stripped = value.strip()
        if enum_values and stripped not in enum_values:
            return None
        return stripped
    return None  # text는 비교하지 않는다.


def dates_compatible(values: set[str]) -> bool:
    """정밀도만 다른 날짜 값들이 같은 시점으로 겹치면 True를 준다.

    "2026-09"와 "2026-09-15"는 다른 주장이 아니라 같은 시점을 다른
    정밀도로 말한 것이다. 가장 정밀한 값 하나를 나머지 전부가
    구간 접두로 포함해야 겹침이다. 같은 정밀도의 서로 다른 값이
    섞이면 겹침이 아니다.
    """
    longest = max(values, key=len)
    return all(
        value == longest or longest.startswith(value + "-")
        for value in values
    )
