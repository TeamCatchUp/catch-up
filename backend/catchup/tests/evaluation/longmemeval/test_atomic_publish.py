"""산출물 묶음이 한 run 단위로만 보이는지 못 박는다.

QA 러너가 N번째 문항에서 깨지면 앞의 N-1건은 이미 파일에 있다. 그것이
완주본으로 읽히면 채점기는 줄어든 분모 위에서 점수를 낸다 — 못 푼 문항이
뒤쪽에 몰린 실행일수록 점수가 높아진다. 그래서 "전 문항 성공 뒤에만
포인터가 그 run을 가리킨다"를 고정한다.

묶음의 원자성도 같이 못 박는다. 세 파일을 하나씩 최종 경로로 옮기면 같은
출력 디렉토리로 도는 두 실행이 results는 B, trace·usage는 A인 묶음을
남긴다. 답변은 B인데 실패 귀속과 비용은 A로 읽히므로 진단이 통째로
거짓이 된다. 그래서 run 디렉토리를 완성한 뒤 포인터 하나만 바꾼다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catchup.evaluation.longmemeval.atomic_publish import POINTER_FILENAME
from catchup.evaluation.longmemeval.atomic_publish import RUN_STATUS_COMPLETE
from catchup.evaluation.longmemeval.atomic_publish import RUN_STATUS_RUNNING
from catchup.evaluation.longmemeval.atomic_publish import current_run_directory
from catchup.evaluation.longmemeval.atomic_publish import new_run_id
from catchup.evaluation.longmemeval.atomic_publish import pointer_path
from catchup.evaluation.longmemeval.atomic_publish import read_pointer
from catchup.evaluation.longmemeval.atomic_publish import run_directory
from catchup.evaluation.longmemeval.atomic_publish import run_temp_path
from catchup.evaluation.longmemeval.atomic_publish import staged_outputs

RESULTS = "qa_results.jsonl"
TRACE = "qa_trace.jsonl"
USAGE = "qa_usage.json"
BUNDLE = (RESULTS, TRACE, USAGE)


def _write_bundle(paths: tuple[Path, ...], marker: str) -> None:
    """세 산출물에 어느 run이 썼는지 알아볼 표식을 남긴다."""
    for path in paths:
        path.write_text(marker, encoding="utf-8")


def test_the_bundle_becomes_current_only_after_the_block_finishes(
    tmp_path: Path,
) -> None:
    """본문이 끝나야 포인터가 그 run을 완주본으로 가리킨다."""
    with staged_outputs(tmp_path, BUNDLE) as staged:
        paths = staged.paths
        _write_bundle(paths, "done")
        with pytest.raises(SystemExit):
            current_run_directory(tmp_path)

    directory = current_run_directory(tmp_path)
    assert directory == paths[0].parent
    for name in BUNDLE:
        assert (directory / name).read_text(encoding="utf-8") == "done"


def test_a_failure_leaves_no_current_run(tmp_path: Path) -> None:
    """중간에 깨지면 완주본이 없다고 읽힌다."""
    with pytest.raises(RuntimeError):
        with staged_outputs(tmp_path, BUNDLE) as staged:
            staged.paths[0].write_text(
                '{"question_id": "q1"}\n',
                encoding="utf-8",
            )
            raise RuntimeError("두 번째 문항에서 Bedrock이 깨졌다")

    with pytest.raises(SystemExit) as excinfo:
        current_run_directory(tmp_path)

    assert "완주하지 못했다" in str(excinfo.value)


def test_a_failure_does_not_republish_the_previous_run(tmp_path: Path) -> None:
    """지난 실행의 완주본을 이번 실행의 결과로 읽히게 두지 않는다.

    남겨 두면 채점기가 방금 실패한 실행의 결과라고 믿으면서 옛 점수를
    다시 읽는다. 실패했다는 정보는 어디에도 남지 않는다.
    """
    with staged_outputs(tmp_path, BUNDLE) as staged:
        _write_bundle(staged.paths, "old")
    old_directory = staged.directory

    with pytest.raises(RuntimeError):
        with staged_outputs(tmp_path, BUNDLE):
            raise RuntimeError("적재 실패")

    with pytest.raises(SystemExit):
        current_run_directory(tmp_path)
    # 옛 run 디렉토리 자체는 남는다. 사후 진단에서 직전 실행과 무엇이
    # 달라졌는지를 그대로 열어 볼 수 있어야 한다.
    assert (old_directory / RESULTS).read_text(encoding="utf-8") == "old"


def test_a_failed_run_keeps_its_partial_files_for_diagnosis(
    tmp_path: Path,
) -> None:
    """깨진 run의 부분 산출물은 자기 디렉토리에 그대로 남는다."""
    with pytest.raises(RuntimeError):
        with staged_outputs(tmp_path, BUNDLE) as staged:
            staged.paths[0].write_text("partial", encoding="utf-8")
            raise RuntimeError("적재 실패")

    assert staged.paths[0].read_text(encoding="utf-8") == "partial"


def test_interleaved_runs_never_mix_their_bundles(tmp_path: Path) -> None:
    """두 실행이 교차로 끝나도 완주본 세 파일은 한 run의 것이다.

    파일별 `os.replace`는 results만 B, trace·usage는 A인 묶음을 남긴다.
    답변은 B인데 실패 귀속과 비용은 A로 읽혀 진단이 거짓이 된다.

    A 시작 → B 시작 → B 성공 → A 성공 순서다. 늦게 끝난 A는 포인터를
    이미 B가 가져갔으므로 덮지 않는다 — 최신 실행이 B이기 때문이다.
    """
    first = staged_outputs(tmp_path, BUNDLE, run_id="A")
    second = staged_outputs(tmp_path, BUNDLE, run_id="B")
    first_staged = first.__enter__()
    second_staged = second.__enter__()

    _write_bundle(first_staged.paths, "A")
    _write_bundle(second_staged.paths, "B")
    # B가 먼저 끝나고 A가 나중에 끝난다.
    second.__exit__(None, None, None)
    first.__exit__(None, None, None)

    assert read_pointer(tmp_path) == {
        "run_id": "B",
        "status": RUN_STATUS_COMPLETE,
    }
    directory = current_run_directory(tmp_path)
    markers = {
        (directory / name).read_text(encoding="utf-8") for name in BUNDLE
    }
    assert markers == {"B"}


def test_an_older_success_never_hides_a_newer_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """오래된 완료가 최신 실행의 실패를 덮지 못한다.

    A 시작 → B 시작 → A 성공 → B 실패 순서다. A가 소유권을 보지 않고
    완료를 쓰면 포인터가 `A/complete`로 되살아나, 최신 실행 B가 실패한
    사실이 사라지고 채점기가 A를 현재 완주본으로 읽는다.
    """
    first = staged_outputs(tmp_path, BUNDLE, run_id="A")
    second = staged_outputs(tmp_path, BUNDLE, run_id="B")
    first_staged = first.__enter__()
    second.__enter__()

    _write_bundle(first_staged.paths, "A")
    first.__exit__(None, None, None)
    error = RuntimeError("B가 두 번째 문항에서 깨졌다")
    # 예외를 삼키지 않는다 — 호출한 쪽의 `with`가 그대로 다시 낸다.
    assert second.__exit__(RuntimeError, error, error.__traceback__) is False

    assert read_pointer(tmp_path) == {
        "run_id": "B",
        "status": RUN_STATUS_RUNNING,
    }
    with pytest.raises(SystemExit) as excinfo:
        current_run_directory(tmp_path)
    assert "완주하지 못했다" in str(excinfo.value)
    # A의 결과 자체는 자기 디렉토리에 그대로 남아 사후 진단에 쓰인다.
    assert (run_directory(tmp_path, run_id="A") / RESULTS).read_text(
        encoding="utf-8"
    ) == "A"
    captured = capsys.readouterr()
    assert "포인터를 넘기지 않는다" in captured.out
    assert "포인터를 넘기지 않는다" in captured.err


def test_the_handle_says_whether_this_run_became_current(
    tmp_path: Path,
) -> None:
    """포인터를 넘겼는지를 핸들이 호출한 쪽에 말해 준다.

    경고 출력은 사람만 읽는다. 러너가 exit 코드를 정하려면 코드가 읽을
    값이 있어야 한다 — 없으면 빼앗긴 run도 성공으로 끝난다.
    """
    first = staged_outputs(tmp_path, BUNDLE, run_id="A")
    second = staged_outputs(tmp_path, BUNDLE, run_id="B")
    first_staged = first.__enter__()
    second_staged = second.__enter__()

    _write_bundle(first_staged.paths, "A")
    _write_bundle(second_staged.paths, "B")
    second.__exit__(None, None, None)
    first.__exit__(None, None, None)

    assert first_staged.taken_over is True
    assert second_staged.taken_over is False
    assert first_staged.run_id == "A"
    assert first_staged.directory == run_directory(tmp_path, run_id="A")
    assert first_staged.paths[0].parent == first_staged.directory


def test_the_pointer_names_the_run_it_points_at(tmp_path: Path) -> None:
    """포인터는 run_id와 완주 여부를 담은 파일 하나다."""
    run_id = new_run_id()

    with staged_outputs(tmp_path, BUNDLE, run_id=run_id) as staged:
        _write_bundle(staged.paths, "done")

    pointer = read_pointer(tmp_path)
    assert pointer == {"run_id": run_id, "status": RUN_STATUS_COMPLETE}
    assert pointer_path(tmp_path).name == POINTER_FILENAME
    assert current_run_directory(tmp_path) == run_directory(
        tmp_path,
        run_id=run_id,
    )


def test_a_missing_pointer_is_refused_instead_of_read_flat(
    tmp_path: Path,
) -> None:
    """포인터가 없으면 디렉토리에 바로 놓인 옛 산출물을 읽지 않는다.

    하위 호환으로 flat 파일을 읽어 주면 서로 다른 run이 섞인 묶음을 다시
    채점하게 된다. 섞임 위험을 되살리느니 재실행을 요구한다.
    """
    (tmp_path / RESULTS).write_text(
        '{"question_id": "q1"}\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        current_run_directory(tmp_path)

    assert "포인터가 없다" in str(excinfo.value)


def test_a_half_written_pointer_never_becomes_visible(tmp_path: Path) -> None:
    """포인터는 임시 파일에 다 쓴 뒤 원자적으로 교체된다."""
    with staged_outputs(tmp_path, BUNDLE) as staged:
        _write_bundle(staged.paths, "done")

    assert json.loads(pointer_path(tmp_path).read_text(encoding="utf-8"))
    leftovers = [
        path
        for path in tmp_path.iterdir()
        if path.name.startswith(f"{POINTER_FILENAME}.tmp")
    ]
    assert leftovers == []


def test_each_run_stages_into_its_own_directory(tmp_path: Path) -> None:
    """실행마다 다른 run 디렉토리를 쓴다."""
    first = run_directory(tmp_path, run_id=new_run_id())
    second = run_directory(tmp_path, run_id=new_run_id())

    assert first != second
    assert first.parent == second.parent


def test_run_temp_path_stays_in_the_same_directory() -> None:
    """단일 파일 publish의 임시 경로는 최종 경로와 같은 디렉토리에 둔다.

    `os.replace`가 원자적인 것은 같은 파일시스템 안에서일 때뿐이다.
    """
    path = Path("/tmp/results/manifest.json")

    temporary = run_temp_path(path, run_id=new_run_id())

    assert temporary.parent == path.parent
