"""LongMemEval oracle 데이터셋 모듈의 순수 함수를 검증한다."""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from catchup.evaluation.longmemeval.dataset import bootstrap_sessions
from catchup.evaluation.longmemeval.dataset import load_oracle
from catchup.evaluation.longmemeval.dataset import parse_lme_date
from catchup.evaluation.longmemeval.dataset import select_subset


def _turn(role: str, content: str, has_answer: bool = False) -> dict[str, Any]:
    """oracle 원본과 같은 모양의 턴 dict를 만든다.

    증거 턴에만 `has_answer` 키가 존재하는 원본 규칙을 그대로 따른다.
    """
    turn: dict[str, Any] = {"role": role, "content": content}
    if has_answer:
        turn["has_answer"] = True
    return turn


def _question(
    question_id: str,
    question_type: str,
    *,
    session_ids: list[str],
    dates: list[str],
    answer_session_ids: list[str] | None = None,
) -> dict[str, Any]:
    """세션 개수만큼 턴을 채운 질문 dict를 만든다."""
    sessions = [
        [
            _turn("user", f"{sid} 사용자 발화", has_answer=True),
            _turn("assistant", f"{sid} 어시스턴트 발화"),
        ]
        for sid in session_ids
    ]
    return {
        "question_id": question_id,
        "question_type": question_type,
        "question": f"{question_id} 질문",
        "answer": f"{question_id} 답",
        "question_date": "2023/05/20 (Sat) 10:00",
        "haystack_session_ids": session_ids,
        "haystack_dates": dates,
        "haystack_sessions": sessions,
        "answer_session_ids": (
            answer_session_ids
            if answer_session_ids is not None
            else [session_ids[0]]
        ),
    }


def _write(path: Path, questions: list[dict[str, Any]]) -> Path:
    """질문 목록을 oracle과 같은 JSON 배열 파일로 저장한다."""
    path.write_text(json.dumps(questions), encoding="utf-8")
    return path


MINI_QUESTIONS: list[dict[str, Any]] = [
    _question(
        "q_ku_01",
        "knowledge-update",
        session_ids=["s_c", "s_a", "s_b"],
        dates=[
            "2023/04/12 (Wed) 09:30",
            "2023/04/10 (Mon) 23:07",
            "2023/04/11 (Tue) 08:00",
        ],
        answer_session_ids=["s_a", "s_b"],
    ),
    _question(
        "q_tr_01",
        "temporal-reasoning",
        session_ids=["t_a", "t_b"],
        dates=["2023/03/01 (Wed) 12:00", "2023/03/02 (Thu) 12:00"],
    ),
    _question(
        "q_ms_01_abs",
        "multi-session",
        session_ids=["m_a"],
        dates=["2023/02/01 (Wed) 07:45"],
        answer_session_ids=[],
    ),
]


def test_parse_lme_date_returns_utc_aware_datetime() -> None:
    """oracle 날짜 문자열을 UTC aware datetime으로 읽는다."""
    parsed = parse_lme_date("2023/04/10 (Mon) 23:07")

    assert parsed == datetime(2023, 4, 10, 23, 7, tzinfo=timezone.utc)
    assert parsed.tzinfo is timezone.utc
    assert parsed.utcoffset() is not None


def test_load_oracle_sorts_sessions_in_timestamp_order(tmp_path: Path) -> None:
    """세션을 timestamp 오름차순으로 정렬하고 id·date 짝을 유지한다."""
    path = _write(tmp_path / "oracle.json", MINI_QUESTIONS)

    questions = load_oracle(path)

    first = questions[0]
    assert [s.session_id for s in first.sessions] == ["s_a", "s_b", "s_c"]
    assert [s.timestamp for s in first.sessions] == [
        datetime(2023, 4, 10, 23, 7, tzinfo=timezone.utc),
        datetime(2023, 4, 11, 8, 0, tzinfo=timezone.utc),
        datetime(2023, 4, 12, 9, 30, tzinfo=timezone.utc),
    ]


def test_load_oracle_keeps_question_fields(tmp_path: Path) -> None:
    """질문 메타데이터와 증거 세션 집합을 그대로 보존한다."""
    path = _write(tmp_path / "oracle.json", MINI_QUESTIONS)

    questions = load_oracle(path)
    by_id = {q.question_id: q for q in questions}

    first = by_id["q_ku_01"]
    assert first.question_type == "knowledge-update"
    assert first.question == "q_ku_01 질문"
    assert first.answer == "q_ku_01 답"
    assert first.question_date == datetime(
        2023, 5, 20, 10, 0, tzinfo=timezone.utc
    )
    assert first.answer_session_ids == frozenset({"s_a", "s_b"})
    assert by_id["q_ms_01_abs"].answer_session_ids == frozenset()


def test_load_oracle_preserves_turns(tmp_path: Path) -> None:
    """턴의 role·content를 보존하고 `has_answer` 결측을 False로 채운다."""
    path = _write(tmp_path / "oracle.json", MINI_QUESTIONS)

    session = load_oracle(path)[0].sessions[0]

    assert [t.role for t in session.turns] == ["user", "assistant"]
    assert session.turns[0].content == "s_a 사용자 발화"
    assert session.turns[0].has_answer is True
    assert session.turns[1].has_answer is False


def _bucket_questions() -> list[dict[str, Any]]:
    """서브셋 선정을 검증할 다중 유형 질문 목록을 만든다."""
    questions: list[dict[str, Any]] = []
    types = {
        "knowledge-update": "ku",
        "temporal-reasoning": "tr",
        "multi-session": "ms",
        "single-session-user": "su",
    }
    for question_type, prefix in types.items():
        for index in range(3):
            sid = f"{prefix}{index}_s"
            questions.append(
                _question(
                    f"{prefix}_{index:02d}",
                    question_type,
                    session_ids=[sid],
                    dates=["2023/01/01 (Sun) 00:00"],
                )
            )
            abs_sid = f"{prefix}{index}_abs_s"
            questions.append(
                _question(
                    f"{prefix}_{index:02d}_abs",
                    question_type,
                    session_ids=[abs_sid],
                    dates=["2023/01/01 (Sun) 00:00"],
                )
            )
    return questions


def test_select_subset_builds_four_deterministic_buckets(
    tmp_path: Path,
) -> None:
    """세 유형 비-abs 버킷과 abstention 버킷을 사전순으로 뽑는다."""
    path = _write(tmp_path / "oracle.json", _bucket_questions())
    questions = load_oracle(path)

    subset = select_subset(questions, per_type=2)

    assert [q.question_id for q in subset] == [
        "ku_00",
        "ku_01",
        "tr_00",
        "tr_01",
        "ms_00",
        "ms_01",
        "ku_00_abs",
        "ku_01_abs",
    ]


def test_select_subset_excludes_other_question_types(tmp_path: Path) -> None:
    """ku·tr·ms 밖의 유형은 비-abs도 abs도 뽑지 않는다."""
    path = _write(tmp_path / "oracle.json", _bucket_questions())
    questions = load_oracle(path)

    subset = select_subset(questions, per_type=10)

    assert all(not q.question_id.startswith("su_") for q in subset)


def test_select_subset_is_order_independent(tmp_path: Path) -> None:
    """입력 순서를 뒤집어도 같은 서브셋을 돌려준다."""
    path = _write(tmp_path / "oracle.json", _bucket_questions())
    questions = load_oracle(path)

    forward = select_subset(questions, per_type=2)
    backward = select_subset(list(reversed(questions)), per_type=2)

    assert [q.question_id for q in forward] == [
        q.question_id for q in backward
    ]


def test_bootstrap_sessions_excludes_subset_questions(tmp_path: Path) -> None:
    """서브셋 문항의 세션을 부트스트랩 재료에서 제외한다."""
    path = _write(tmp_path / "oracle.json", _bucket_questions())
    questions = load_oracle(path)
    subset = select_subset(questions, per_type=2)
    subset_session_ids = {
        session.session_id for q in subset for session in q.sessions
    }

    sessions = bootstrap_sessions(questions, subset, limit=100)

    assert sessions
    assert not subset_session_ids & {s.session_id for s in sessions}
    assert "su0_s" not in {s.session_id for s in sessions}


def test_bootstrap_sessions_dedupes_and_limits(tmp_path: Path) -> None:
    """중복 session_id를 제거하고 limit 개수까지만 돌려준다."""
    shared = _question(
        "ku_90",
        "knowledge-update",
        session_ids=["shared_s"],
        dates=["2023/01/01 (Sun) 00:00"],
    )
    twin = _question(
        "ku_91",
        "knowledge-update",
        session_ids=["shared_s", "extra_s"],
        dates=["2023/01/01 (Sun) 00:00", "2023/01/02 (Mon) 00:00"],
    )
    path = _write(tmp_path / "oracle.json", [shared, twin])
    questions = load_oracle(path)

    sessions = bootstrap_sessions(questions, [], limit=100)
    limited = bootstrap_sessions(questions, [], limit=1)

    assert [s.session_id for s in sessions] == ["shared_s", "extra_s"]
    assert [s.session_id for s in limited] == ["shared_s"]
