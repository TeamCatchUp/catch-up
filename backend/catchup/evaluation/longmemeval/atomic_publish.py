"""완주한 실행의 산출물만 최종 경로에 나타나게 한다.

평가 러너의 산출물은 전부 "완주했는가"를 함께 말한다. 중간에 깨진
실행이 최종 경로에 절반짜리 파일을 남기면, 그 뒤에 오는 채점기나
오케스트레이터는 그것을 완주 결과로 읽고 줄어든 분모 위에서 점수를
낸다. 실패한 실행의 점수가 오히려 높아지는 일이 그 경로로 생긴다.

그래서 두 가지를 함께 건다. 하나, 쓰는 동안에는 실행 전용 임시 경로에만
둔다. 둘, 마지막까지 예외 없이 끝났을 때만 `os.replace`로 옮긴다 —
같은 파일시스템 안에서 원자적이라 읽는 쪽이 보는 것은 완성본 아니면
아무것도 없음, 둘 중 하나다.

임시 경로에 실행 ID를 붙이는 것도 같은 이유다. 고정된 `.tmp` 하나를
나눠 쓰면 같은 경로로 동시에 도는 두 실행이 서로의 임시 파일을 덮고,
먼저 끝난 쪽이 남의 미완성 산출물을 공개한다.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path

__all__ = [
    "RUN_TEMP_SUFFIX",
    "new_run_id",
    "publish_run_file",
    "run_temp_path",
    "staged_outputs",
]

RUN_TEMP_SUFFIX = ".tmp"
"""공개 전 산출물이 머무는 임시 경로의 접미사를 나타낸다."""


def new_run_id() -> str:
    """이번 실행의 임시 파일을 남과 갈라놓을 ID를 만든다.

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


@contextmanager
def staged_outputs(
    paths: Sequence[Path],
    *,
    run_id: str | None = None,
) -> Iterator[tuple[Path, ...]]:
    """산출물 묶음을 임시 경로에 쓰게 하고 성공했을 때만 공개한다.

    들어가면서 최종 경로의 옛 산출물을 먼저 지운다. 지우지 않으면 이번
    실행이 중간에 깨져도 지난 실행의 완주본이 최종 경로에 그대로 남아,
    채점기는 방금 실패한 실행의 결과를 읽고 있다고 믿는다.

    예외로 빠져나가면 임시 파일도 지운다. 묶음 중 일부만 공개되는 일도
    없다 — 결과와 trace가 어긋난 채로 남으면 진단이 갈라진다.

    Yields:
        최종 경로와 같은 순서의 임시 경로들을 내보낸다.
    """
    identifier = new_run_id() if run_id is None else run_id
    temporaries = tuple(
        run_temp_path(path, run_id=identifier) for path in paths
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
    try:
        yield temporaries
    except BaseException:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)
        raise
    for path, temporary in zip(paths, temporaries, strict=True):
        publish_run_file(path, temporary)
