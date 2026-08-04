"""완주한 실행의 산출물 묶음만, 통째로, 최종적으로 보이게 한다.

평가 러너의 산출물은 전부 "완주했는가"를 함께 말한다. 중간에 깨진
실행이 최종 경로에 절반짜리 파일을 남기면, 그 뒤에 오는 채점기나
오케스트레이터는 그것을 완주 결과로 읽고 줄어든 분모 위에서 점수를
낸다. 실패한 실행의 점수가 오히려 높아지는 일이 그 경로로 생긴다.

파일 하나씩 `os.replace`하는 방식으로는 여기까지밖에 못 간다. 원자적인
것은 파일 하나의 교체뿐이라, 같은 출력 디렉토리로 두 실행이 동시에
끝나면 results는 B, trace·usage는 A인 묶음이 남는다. 답변은 B인데 실패
귀속과 비용은 A로 읽히므로 진단이 통째로 거짓이 된다.

그래서 경계를 파일이 아니라 run에 둔다.

1. 실행마다 `<output>/runs/<run_id>/` 아래에 산출물을 전부 쓴다. 다른
   실행과 경로가 겹치지 않으므로 서로의 파일을 덮을 길이 없다.
2. 어느 run이 현재인지는 포인터 파일 `<output>/current_run.json` 하나가
   말한다. 이 파일 하나만 원자적으로 교체하면 되므로, 읽는 쪽이 어느
   시점에 보든 세 파일은 늘 같은 run의 것이다.
3. 포인터는 시작할 때 `running`으로, 끝까지 예외 없이 갔을 때만
   `complete`로 바뀐다. 중간에 깨지면 포인터는 `running`에 멈추고 읽는
   쪽은 시끄럽게 거절한다 — 지난 실행의 완주본을 방금 실패한 실행의
   결과라고 믿으면서 옛 점수를 다시 읽는 일이 그래야 막힌다.

옛 run 디렉토리는 지우지 않는다. 포인터가 현재를 정하므로 남아 있어도
오독되지 않고, 깨진 실행이 어디까지 갔는지·직전 실행과 무엇이 달라졌는지를
나중에 그대로 열어 볼 수 있다.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

__all__ = [
    "POINTER_FILENAME",
    "RUNS_DIRNAME",
    "RUN_STATUS_COMPLETE",
    "RUN_STATUS_RUNNING",
    "RUN_TEMP_SUFFIX",
    "current_run_directory",
    "new_run_id",
    "pointer_path",
    "publish_run_file",
    "read_pointer",
    "run_directory",
    "run_temp_path",
    "staged_outputs",
    "write_pointer",
]

RUN_TEMP_SUFFIX = ".tmp"
"""공개 전 파일이 머무는 임시 경로의 접미사를 나타낸다."""

RUNS_DIRNAME = "runs"
"""실행별 산출물 디렉토리가 모이는 하위 디렉토리 이름을 나타낸다."""

POINTER_FILENAME = "current_run.json"
"""어느 run이 현재인지 가리키는 포인터 파일 이름을 나타낸다."""

RUN_STATUS_RUNNING = "running"
"""아직 완주하지 못한 run을 가리키는 포인터 상태를 나타낸다."""

RUN_STATUS_COMPLETE = "complete"
"""끝까지 성공한 run을 가리키는 포인터 상태를 나타낸다."""


def new_run_id() -> str:
    """이번 실행을 남과 갈라놓을 ID를 만든다.

    pid만 쓰면 오래 도는 러너 사이에서 번호가 재사용될 수 있고, 컨테이너
    두 개가 같은 볼륨을 보면 pid 자체가 겹친다. 그래서 사람이 읽을 pid에
    난수를 덧붙인다 — 진단할 때 어느 프로세스가 남긴 파일인지 보인다.
    """
    return f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


def run_temp_path(path: Path, *, run_id: str) -> Path:
    """최종 경로에 대응하는 이 실행 전용 임시 경로를 만든다.

    같은 디렉토리에 둔다. `os.replace`가 원자적인 것은 같은 파일시스템
    안에서일 때뿐이라, 임시 파일을 시스템 temp에 두면 그 보장이 사라진다.
    """
    return path.with_name(f"{path.name}{RUN_TEMP_SUFFIX}.{run_id}")


def publish_run_file(path: Path, temporary: Path) -> None:
    """이 실행이 쓴 임시 파일만 최종 경로로 원자적으로 옮긴다.

    옮길 임시 경로를 인자로 받는 것이 요점이다. 최종 경로에서 임시 경로를
    다시 계산하면 남이 만든 임시 파일을 공개할 수 있다.
    """
    os.replace(temporary, path)


def run_directory(output: Path, *, run_id: str) -> Path:
    """실행 하나가 산출물을 모아 둘 디렉토리 경로를 만든다."""
    return output / RUNS_DIRNAME / run_id


def pointer_path(output: Path) -> Path:
    """현재 run을 가리키는 포인터 파일 경로를 만든다."""
    return output / POINTER_FILENAME


def write_pointer(output: Path, *, run_id: str, status: str) -> None:
    """포인터를 원자적으로 교체한다.

    임시 파일에 다 쓴 뒤 `os.replace`로 옮긴다. 최종 경로에 바로 쓰면
    읽는 쪽이 반쯤 쓰인 JSON을 볼 수 있고, 그 순간 어느 run이 현재인지에
    대한 답이 사라진다.
    """
    path = pointer_path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = run_temp_path(path, run_id=run_id)
    temporary.write_text(
        json.dumps({"run_id": run_id, "status": status}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    publish_run_file(path, temporary)


def read_pointer(output: Path) -> dict[str, Any] | None:
    """포인터를 읽어 dict로 돌려준다. 없으면 None이다."""
    path = pointer_path(output)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def current_run_directory(output: Path) -> Path:
    """완주한 현재 run의 디렉토리를 돌려준다.

    포인터가 없거나 완주를 말하지 않으면 거절한다. 옛 flat 산출물을
    읽어 주는 하위 호환 경로는 두지 않는다 — 그 경로를 열어 두면 서로
    다른 run의 결과·trace·usage가 섞인 묶음을 다시 읽게 된다.

    Raises:
        SystemExit: 포인터가 없거나 run이 완주하지 못했을 때 낸다.
    """
    pointer = read_pointer(output)
    if pointer is None:
        raise SystemExit(
            f"완주한 run 포인터가 없다: {pointer_path(output)}. "
            "러너를 다시 완주시킨다. 예전 방식으로 디렉토리에 바로 놓인 "
            "산출물은 읽지 않는다 — 서로 다른 run이 섞였을 수 있다."
        )
    run_id = str(pointer.get("run_id") or "")
    status = str(pointer.get("status") or "")
    if not run_id or status != RUN_STATUS_COMPLETE:
        raise SystemExit(
            f"마지막 run이 완주하지 못했다: run_id={run_id or '?'}, "
            f"status={status or '?'}. 러너를 다시 완주시킨다. 깨진 run의 "
            f"부분 산출물은 {run_directory(output, run_id=run_id)}에 "
            "그대로 남겨 두었다."
        )
    return run_directory(output, run_id=run_id)


@contextmanager
def staged_outputs(
    output: Path,
    filenames: Sequence[str],
    *,
    run_id: str | None = None,
) -> Iterator[tuple[Path, ...]]:
    """산출물 묶음을 run 디렉토리에 쓰게 하고 완주했을 때만 공개한다.

    들어가면서 포인터를 이번 run의 `running`으로 바꾼다. 그 순간부터
    읽는 쪽은 완주한 run이 없다고 본다. 지난 실행의 완주본을 그대로
    가리키게 두면, 이번 실행이 깨졌을 때 채점기가 방금 실패한 실행의
    결과라고 믿으면서 옛 점수를 다시 읽는다.

    나가면서 예외가 없었을 때만 포인터를 `complete`로 바꾼다. 파일 하나가
    아니라 포인터 하나를 교체하는 것이라, 같은 출력 디렉토리로 두 실행이
    동시에 끝나도 읽는 쪽이 보는 세 파일은 늘 한 run의 것이다.

    Yields:
        `filenames`와 같은 순서의 run 디렉토리 안 경로들을 내보낸다.
    """
    identifier = new_run_id() if run_id is None else run_id
    directory = run_directory(output, run_id=identifier)
    directory.mkdir(parents=True, exist_ok=True)
    write_pointer(output, run_id=identifier, status=RUN_STATUS_RUNNING)
    yield tuple(directory / name for name in filenames)
    write_pointer(output, run_id=identifier, status=RUN_STATUS_COMPLETE)
