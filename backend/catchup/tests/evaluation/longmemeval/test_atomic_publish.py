"""부분 산출물이 완주 결과로 보이지 않는지 못 박는다.

QA 러너가 N번째 문항에서 깨지면 앞의 N-1건은 이미 파일에 있다. 그
파일이 최종 이름으로 남으면 채점기는 그것을 완주 결과로 읽고 줄어든
분모 위에서 점수를 낸다 — 못 푼 문항이 뒤쪽에 몰린 실행일수록 점수가
높아진다. 그래서 "전 문항 성공 뒤에만 최종 경로에 나타난다"를 고정한다.

지난 실행의 완주본이 최종 경로에 남는 경로도 같이 막는다. 방금 실패한
실행의 결과라고 믿으면서 옛 점수를 다시 읽게 되기 때문이다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from catchup.evaluation.longmemeval.atomic_publish import new_run_id
from catchup.evaluation.longmemeval.atomic_publish import run_temp_path
from catchup.evaluation.longmemeval.atomic_publish import staged_outputs


def test_outputs_appear_only_after_the_block_finishes(tmp_path: Path) -> None:
    """본문이 끝나야 최종 경로에 산출물이 나타난다."""
    results = tmp_path / "qa_results.jsonl"
    usage = tmp_path / "qa_usage.json"

    with staged_outputs((results, usage)) as (results_temp, usage_temp):
        results_temp.write_text("{}\n", encoding="utf-8")
        usage_temp.write_text("{}\n", encoding="utf-8")
        assert not results.exists()
        assert not usage.exists()

    assert results.read_text(encoding="utf-8") == "{}\n"
    assert usage.read_text(encoding="utf-8") == "{}\n"
    assert not results_temp.exists()
    assert not usage_temp.exists()


def test_a_failure_leaves_no_final_output(tmp_path: Path) -> None:
    """중간에 깨지면 최종 경로에 부분 산출물이 남지 않는다."""
    results = tmp_path / "qa_results.jsonl"
    usage = tmp_path / "qa_usage.json"

    with pytest.raises(RuntimeError):
        with staged_outputs((results, usage)) as (results_temp, _usage_temp):
            results_temp.write_text('{"question_id": "q1"}\n', encoding="utf-8")
            raise RuntimeError("두 번째 문항에서 Bedrock이 깨졌다")

    assert not results.exists()
    assert not usage.exists()
    assert list(tmp_path.iterdir()) == []


def test_a_failure_removes_the_previous_run_output(tmp_path: Path) -> None:
    """지난 실행의 완주본도 남기지 않는다.

    남겨 두면 채점기가 방금 실패한 실행의 결과라고 믿으면서 옛 점수를
    다시 읽는다. 실패했다는 정보는 어디에도 남지 않는다.
    """
    results = tmp_path / "qa_results.jsonl"
    results.write_text('{"question_id": "old"}\n', encoding="utf-8")

    with pytest.raises(RuntimeError):
        with staged_outputs((results,)):
            raise RuntimeError("적재 실패")

    assert not results.exists()


def test_each_run_stages_into_its_own_temp_path(tmp_path: Path) -> None:
    """실행마다 다른 임시 경로를 쓴다."""
    path = tmp_path / "qa_results.jsonl"

    first = run_temp_path(path, run_id=new_run_id())
    second = run_temp_path(path, run_id=new_run_id())

    assert first != second
    assert first.parent == path.parent
