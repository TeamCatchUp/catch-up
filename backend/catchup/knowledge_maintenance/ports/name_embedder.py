"""엔티티 이름을 벡터로 바꾸는 포트를 정의한다.

여기서 얻은 벡터는 해소 단계에서 "같은 판정대에 올릴 후보 블록"을 만드는
데에만 쓴다. 판정 권위는 identity judge에게, 병합 확정 권위는 사람에게
그대로 있고, 유사도는 누구를 판정대에 올릴지만 정한다.

컴파일러로는 반입하지 않는다. 컴파일은 같은 입력에 같은 문서를 내야 하는
결정론 단계라 모델 출력이 끼면 그 성질이 깨진다. knowledge_maintenance가
vector DB를 직접 import하지 않는 규칙도 이 포트로 지킨다. 어댑터만 임베딩
인프라를 알고, 서비스는 이름 목록과 벡터 목록만 본다.

sync로 정의한다. identity judge 포트와 같은 이유로, 서비스와 러너가
이벤트 루프를 몰라도 되도록 비동기 호출은 어댑터가 감싼다.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class NameEmbeddingError(RuntimeError):
    """이름 벡터를 얻지 못했음을 알린다.

    호출자는 이 예외를 이번 라운드의 유사도 blocking을 접는 신호로 읽는다.
    벡터가 없으면 후보군이 정확 일치 경로로 좁아질 뿐이고, 해소 자체가
    멈출 이유는 아니다.
    """


class NameEmbedder(Protocol):
    """이름 목록을 같은 순서의 벡터 목록으로 바꾸는 기능을 정의한다."""

    def embed(self, names: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """이름마다 벡터 하나를 돌려준다.

        Args:
            names: 벡터로 바꿀 이름들을 받는다. 빈 이름은 허용하지 않는다.

        Returns:
            입력과 같은 길이·같은 순서의 벡터들을 돌려준다. 부르는 쪽이
            자리 번호로 이름과 벡터를 짝지으므로 순서가 계약이다.

        Raises:
            NameEmbeddingError: 이름이 비었거나, 호출이 실패했거나, 받은
                벡터 수가 이름 수와 다를 때 던진다.
        """
        ...
