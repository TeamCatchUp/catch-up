"""LongMemEval oracle 데이터셋을 읽어 파이프라인 입력으로 바꾼다.

DB와 LLM에 의존하지 않는 순수 데이터 모듈이다. 파일을 읽고 dataclass로
옮기는 일만 하며, 그 위의 ingestion·평가 단계는 다른 모듈이 맡는다.

원본 파일은 `backend/experiments/longmemeval/longmemeval_oracle.json`이며
질문 500건짜리 JSON 배열이다. 용량이 커서 커밋하지 않는다.

원본 스키마에서 조심할 점이 둘 있다.

1. `haystack_session_ids`·`haystack_dates`·`haystack_sessions`는 같은
   인덱스끼리 짝을 이루지만 시간순이 아니다. 그래서 세 배열을 zip한 뒤
   timestamp 오름차순으로 정렬해 `OracleQuestion.sessions`에 담는다.
2. 턴의 `has_answer` 키는 증거 턴에만 존재한다. 없으면 False로 채운다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

LME_DATE_FORMAT = "%Y/%m/%d %H:%M"
"""요일 토큰을 벗겨낸 뒤 쓰는 날짜 형식을 나타낸다."""

LME_WEEKDAY_TOKEN = re.compile(r"\s*\([^()]*\)\s*")
"""날짜 문자열 안의 요일 괄호 토큰을 나타낸다. 예: ` (Mon) `."""

ABSTENTION_SUFFIX = "_abs"
"""abstention 문항의 question_id 접미사를 나타낸다."""

SUBSET_QUESTION_TYPES: tuple[str, ...] = (
    "knowledge-update",
    "temporal-reasoning",
    "multi-session",
)
"""서브셋과 부트스트랩에서 다루는 질문 유형을 순서대로 나타낸다."""


@dataclass(frozen=True, slots=True)
class OracleTurn:
    """세션 안의 발화 한 줄을 담는다.

    Attributes:
        role: 발화 주체를 나타낸다. `user` 또는 `assistant`이다.
        content: 발화 본문을 담는다.
        has_answer: 정답 근거가 되는 증거 턴인지를 나타낸다.
    """

    role: str
    content: str
    has_answer: bool


@dataclass(frozen=True, slots=True)
class OracleSession:
    """한 시점의 대화 세션을 담는다.

    Attributes:
        session_id: haystack 안에서 세션을 가리키는 식별자를 나타낸다.
        timestamp: 세션이 일어난 시각을 UTC aware datetime으로 담는다.
        turns: 원본 순서를 유지한 발화 목록을 담는다.
    """

    session_id: str
    timestamp: datetime
    turns: tuple[OracleTurn, ...]


@dataclass(frozen=True, slots=True)
class OracleQuestion:
    """질문 한 건과 그 haystack 전체를 담는다.

    Attributes:
        question_id: 질문 식별자를 나타낸다. abstention은 `_abs`로 끝난다.
        question_type: `knowledge-update` 같은 질문 유형을 나타낸다.
        question: 질문 본문을 담는다.
        answer: 정답 문자열을 담는다.
        question_date: 질문 시각을 UTC aware datetime으로 담는다.
        sessions: timestamp 오름차순으로 정렬된 세션 목록을 담는다.
        answer_session_ids: 정답 근거 세션의 식별자 집합을 담는다.
    """

    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: datetime
    sessions: tuple[OracleSession, ...]
    answer_session_ids: frozenset[str]

    @property
    def is_abstention(self) -> bool:
        """답을 거절해야 하는 abstention 문항인지 알려준다."""
        return self.question_id.endswith(ABSTENTION_SUFFIX)


def parse_lme_date(raw: str) -> datetime:
    """oracle 날짜 문자열을 UTC aware datetime으로 바꾼다.

    원본에는 시간대 정보가 없다. 데이터셋 전체를 하나의 시간축에 놓으려고
    UTC로 고정해 읽는다.

    요일 괄호 토큰(` (Mon) `)은 파싱 전에 정규식으로 벗겨낸다.
    `%a`로 읽으면 프로세스 로케일에 따라 같은 파일이 어디서는 읽히고
    어디서는 `ValueError`가 난다. 날짜 값은 연·월·일·시·분만으로 이미
    정해지므로 요일은 버려도 정보 손실이 없다.
    """
    normalized = LME_WEEKDAY_TOKEN.sub(" ", raw).strip()
    return datetime.strptime(normalized, LME_DATE_FORMAT).replace(
        tzinfo=timezone.utc
    )


def _parse_turn(raw: Mapping[str, Any]) -> OracleTurn:
    """턴 dict 하나를 `OracleTurn`으로 바꾼다."""
    return OracleTurn(
        role=raw["role"],
        content=raw["content"],
        has_answer=bool(raw.get("has_answer", False)),
    )


def _parse_question(raw: Mapping[str, Any]) -> OracleQuestion:
    """질문 dict 하나를 `OracleQuestion`으로 바꾼다.

    ids·dates·sessions를 zip한 뒤 timestamp 오름차순으로 정렬한다. 같은
    시각이 겹치면 원본 순서를 유지한다(`sorted`는 안정 정렬이다).
    """
    sessions = [
        OracleSession(
            session_id=session_id,
            timestamp=parse_lme_date(date),
            turns=tuple(_parse_turn(turn) for turn in turns),
        )
        for session_id, date, turns in zip(
            raw["haystack_session_ids"],
            raw["haystack_dates"],
            raw["haystack_sessions"],
            strict=True,
        )
    ]
    sessions.sort(key=lambda session: session.timestamp)
    return OracleQuestion(
        question_id=raw["question_id"],
        question_type=raw["question_type"],
        question=raw["question"],
        answer=raw["answer"],
        question_date=parse_lme_date(raw["question_date"]),
        sessions=tuple(sessions),
        answer_session_ids=frozenset(raw.get("answer_session_ids") or ()),
    )


def load_oracle(path: Path) -> list[OracleQuestion]:
    """oracle JSON 파일을 읽어 질문 목록으로 돌려준다.

    질문의 순서는 원본 파일 순서를 그대로 둔다. 순서에 의존하는 선정은
    `select_subset`이 question_id 사전순으로 다시 정한다.
    """
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    return [_parse_question(raw) for raw in payload]


def select_subset(
    questions: Iterable[OracleQuestion],
    *,
    per_type: int = 10,
) -> list[OracleQuestion]:
    """평가용 서브셋을 결정론적으로 고른다.

    버킷은 넷이다. `knowledge-update`·`temporal-reasoning`·`multi-session`
    각각의 비-abstention 문항에서 앞 `per_type`개, 그리고 이 세 유형에
    속하는 abstention 문항에서 앞 `per_type`개를 뽑는다. 다른 유형은
    다루지 않는다.

    난수를 쓰지 않고 question_id 사전순으로만 자른다. 같은 입력이면 입력
    순서와 무관하게 늘 같은 서브셋이 나온다.
    """
    ordered = sorted(questions, key=lambda q: q.question_id)
    selected: list[OracleQuestion] = []
    for question_type in SUBSET_QUESTION_TYPES:
        bucket = [
            question
            for question in ordered
            if question.question_type == question_type
            and not question.is_abstention
        ]
        selected.extend(bucket[:per_type])
    abstentions = [
        question
        for question in ordered
        if question.is_abstention
        and question.question_type in SUBSET_QUESTION_TYPES
    ]
    selected.extend(abstentions[:per_type])
    return selected


def bootstrap_sessions(
    questions: Iterable[OracleQuestion],
    subset: Sequence[OracleQuestion],
    *,
    limit: int = 15,
) -> list[OracleSession]:
    """어휘 부트스트랩에 쓸 세션을 서브셋 밖에서 고른다.

    평가 대상 서브셋으로 어휘를 튜닝하면 성능이 부풀려진다. 그래서
    서브셋에 든 문항과, 서브셋이 쓰는 session_id는 모두 제외한다. 세션
    식별자는 문항끼리 겹치는 경우가 있어서 문항 단위 제외만으로는
    부족하다.

    후보는 `SUBSET_QUESTION_TYPES` 유형의 문항이며, question_id 사전순으로
    훑으면서 중복 session_id를 지우고 앞 `limit`개를 돌려준다.
    """
    subset_question_ids = {question.question_id for question in subset}
    subset_session_ids = {
        session.session_id
        for question in subset
        for session in question.sessions
    }
    candidates = sorted(
        (
            question
            for question in questions
            if question.question_type in SUBSET_QUESTION_TYPES
            and question.question_id not in subset_question_ids
        ),
        key=lambda question: question.question_id,
    )
    collected: list[OracleSession] = []
    seen: set[str] = set(subset_session_ids)
    for question in candidates:
        for session in question.sessions:
            if session.session_id in seen:
                continue
            seen.add(session.session_id)
            collected.append(session)
            if len(collected) >= limit:
                return collected
    return collected
