"""문항마다 어느 workspace에 그 haystack이 들어갔는지를 적어 둔다.

LongMemEval의 문항은 저마다 자기 haystack을 들고 온다. 그 세션을 전부
한 workspace에 부으면 문항 A의 세션에서 나온 지식이 문항 B의 조회에
그대로 걸린다. B가 "모른다"고 답해야 맞는 질문에 A의 사실로 답하게
되므로, 특히 abstention 문항의 점수가 통째로 무의미해진다. 조회 쪽에
문항 필터를 다는 방법은 없다 — as-of 조회의 격리 단위가 workspace라서,
격리도 workspace로 해야 한다.

그래서 수집 러너가 문항 하나당 workspace 하나를 쓴다. 세션이 여러 문항에
겹쳐 나오면 각 문항의 workspace에 각각 넣는다. 중복 적재가 낭비처럼
보이지만, 격리가 목적이므로 그것이 정답이다.

workspace 번호는 난수가 아니라 `base + 서브셋 안의 인덱스`다. 인덱스는
`select_subset`이 정하는 순서이고 그 함수는 question_id 사전순으로만
자르므로, 같은 oracle과 같은 `--per-type`이면 늘 같은 번호가 나온다.
재실행이 같은 곳을 덮어써야 수집을 다시 돌려도 결과가 갈라지지 않는다.

이 파일은 수집 러너가 쓰고 QA·채점 러너가 읽는다. 러너끼리 workspace
번호를 각자 계산하면 한쪽만 `--per-type`을 바꿔도 조용히 어긋나므로,
계산은 한 번만 하고 나머지는 그 결과를 읽기만 한다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catchup.evaluation.longmemeval.dataset import OracleQuestion

__all__ = [
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_WORKSPACE_BASE",
    "WORKSPACE_NAME_MAX_LENGTH",
    "WORKSPACE_NAME_PREFIX",
    "WorkspaceAssignment",
    "assign_workspaces",
    "check_manifest_covers",
    "load_manifest",
    "workspace_by_question",
    "write_manifest",
]

DEFAULT_WORKSPACE_BASE = 910000
"""문항별 workspace 번호의 시작점을 나타낸다.

기존 평가 workspace(902)와 부트스트랩(901)에서 멀리 떨어뜨린다. 한
서브셋이 수백 개의 번호를 쓰므로 가까이 두면 사람이 쓰던 workspace를
덮어쓸 수 있다.
"""

DEFAULT_MANIFEST_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "experiments"
    / "longmemeval"
    / "results"
    / "workspace_manifest.json"
)

WORKSPACE_NAME_PREFIX = "bench-lme-q-"
"""문항별 workspace 이름의 접두사를 나타낸다."""

WORKSPACE_NAME_MAX_LENGTH = 50
"""`workspaces.name` 칸의 길이 상한을 나타낸다."""


def workspace_name(question_id: str) -> str:
    """문항 하나가 쓸 workspace 이름을 만든다.

    `workspaces.name`이 varchar(50)이라 긴 question_id는 잘린다. 이름은
    사람이 읽는 표시일 뿐이고 문항과 workspace를 잇는 것은 manifest이므로,
    잘려도 조회가 어긋나지 않는다.
    """
    return f"{WORKSPACE_NAME_PREFIX}{question_id}"[:WORKSPACE_NAME_MAX_LENGTH]


@dataclass(frozen=True, slots=True)
class WorkspaceAssignment:
    """문항 하나와 그 문항 전용 workspace를 묶어 담는다.

    Attributes:
        question_id: 문항 식별자를 나타낸다.
        workspace_id: 이 문항의 세션만 들어간 workspace를 나타낸다.
        session_ids: 그 workspace에 적재할 세션 식별자를 시간순으로 담는다.
    """

    question_id: str
    workspace_id: int
    session_ids: tuple[str, ...]

    @property
    def workspace_name(self) -> str:
        """이 문항의 workspace 이름을 나타낸다."""
        return workspace_name(self.question_id)

    def as_dict(self) -> dict[str, Any]:
        """manifest 파일에 담을 한 항목으로 바꾼다."""
        return {
            "question_id": self.question_id,
            "workspace_id": self.workspace_id,
            "session_ids": list(self.session_ids),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> WorkspaceAssignment:
        """manifest 항목 하나를 읽어 들인다.

        Raises:
            KeyError: 필수 키가 빠졌을 때 낸다.
            ValueError: workspace_id가 정수가 아닐 때 낸다.
        """
        return cls(
            question_id=str(raw["question_id"]),
            workspace_id=int(raw["workspace_id"]),
            session_ids=tuple(
                str(session_id) for session_id in raw.get("session_ids") or ()
            ),
        )


def assign_workspaces(
    questions: Sequence[OracleQuestion],
    *,
    base: int = DEFAULT_WORKSPACE_BASE,
) -> tuple[WorkspaceAssignment, ...]:
    """서브셋 순서대로 문항마다 workspace 번호를 매긴다.

    번호는 `base + 인덱스`이고 인덱스는 입력 순서다. 호출자가 넘기는
    입력은 `select_subset`의 출력이며 그 함수가 이미 결정론적이므로,
    여기서 다시 정렬하지 않는다 — 두 번 정렬하면 러너마다 다른 순서를
    쓸 여지가 생긴다.

    세션은 문항 안에서 시간순으로 담는다. `OracleQuestion.sessions`가 이미
    timestamp 오름차순이므로 그 순서를 그대로 쓴다.
    """
    return tuple(
        WorkspaceAssignment(
            question_id=question.question_id,
            workspace_id=base + index,
            session_ids=tuple(
                session.session_id for session in question.sessions
            ),
        )
        for index, question in enumerate(questions)
    )


def write_manifest(
    path: Path,
    assignments: Iterable[WorkspaceAssignment],
) -> None:
    """문항-workspace 대응표를 JSON 배열로 쓴다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [assignment.as_dict() for assignment in assignments]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_manifest(path: Path) -> tuple[WorkspaceAssignment, ...]:
    """manifest 파일을 읽어 대응표로 돌려준다.

    Raises:
        ValueError: 최상위가 배열이 아닐 때 낸다. 형식이 어긋난 파일을
            조용히 빈 목록으로 접으면 격리가 꺼진 채 실행이 이어진다.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(
            f"manifest 최상위는 배열이어야 한다: {path}",
        )
    return tuple(WorkspaceAssignment.from_mapping(raw) for raw in payload)


def check_manifest_covers(
    question_ids: Iterable[str],
    workspace_for: Mapping[str, int],
) -> None:
    """채점할 문항이 manifest에 다 적혀 있는지 확인한다.

    빠진 문항을 옛 단일 workspace로 되돌려 읽으면 그 문항만 조용히 남의
    기억을 보게 된다 — 격리를 켠 실행에서 가장 알아채기 어려운 오염이다.
    보통은 manifest를 만든 `--per-type`과 지금 값이 다른 것이므로 멈춘다.

    Raises:
        SystemExit: manifest에 없는 문항이 하나라도 있을 때 낸다.
    """
    missing = sorted(
        question_id
        for question_id in question_ids
        if question_id not in workspace_for
    )
    if not missing:
        return
    preview = ", ".join(missing[:10]) + (" …" if len(missing) > 10 else "")
    raise SystemExit(
        f"manifest에 없는 문항이 {len(missing)}건이다: {preview}. "
        "수집 때와 같은 `--per-type`으로 돌리거나 수집 러너를 다시 "
        "실행해 manifest를 새로 쓴다."
    )


def workspace_by_question(
    assignments: Iterable[WorkspaceAssignment],
) -> dict[str, int]:
    """question_id로 workspace를 찾을 수 있게 편다."""
    return {
        assignment.question_id: assignment.workspace_id
        for assignment in assignments
    }
