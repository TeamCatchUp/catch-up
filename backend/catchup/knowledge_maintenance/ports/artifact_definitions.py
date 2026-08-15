"""아티팩트 정의를 읽는 포트를 정의한다.

정의는 컴파일의 입구다. 무엇을 문서로 만들지 고르는 자리가 "claim이 많은
노드 상위 N개"가 아니라 사람이 채널에 걸어 둔 정의 행이므로, 그 행을
읽어 오는 계약을 따로 둔다. 쓰기는 여기에 없다 — 컴파일은 정의를 읽기만
한다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec


@dataclass(frozen=True, slots=True)
class StoredArtifactDefinition:
    """저장된 정의 한 행을 컴파일이 쓸 수 있는 형태로 담는다.

    Attributes:
        id: 정의 식별자를 나타낸다.
        channel_id: 이 정의가 걸린 채널을 가리킨다.
        kind: 이 정의가 만드는 문서 종류를 나타낸다.
        selection_spec: 역직렬화를 마친 선택 규칙을 담는다. 저장 형태인
            JSONB가 아니라 값 객체로 들고 있어야 컴파일이 저장 형태를
            다시 해석하지 않는다.
        title_prefix: 문서 제목 앞에 붙일 말을 담는다. 지금은 저장소가
            kind와 같은 값으로 채운다. 제목 조립이 읽는 칸을 kind와
            따로 두어, 뒤에 정의마다 다른 제목을 주게 되어도 읽는 쪽을
            고치지 않는다.
    """

    id: uuid.UUID
    channel_id: uuid.UUID
    kind: str
    selection_spec: SelectionSpec
    title_prefix: str


class ArtifactDefinitionRepository(Protocol):
    """정의 행을 읽는 기능을 정의한다.

    workspace 범위는 저장소를 만들 때 정해진다. 문서 저장소와 같은
    관례다 — 메서드마다 workspace를 다시 넘기게 하면 호출자가 그것을
    틀릴 자리가 생기기 때문이다.
    """

    def list_definitions(self) -> tuple[StoredArtifactDefinition, ...]:
        """workspace의 정의를 식별자 사전순으로 모두 읽는다.

        순서를 고정한다. 컴파일 입구의 차례가 실행마다 흔들리면 같은
        지식 상태에서도 검토 큐에 오르는 순서가 달라진다.

        선택 규칙이 깨진 행을 만나면 건너뛰지 않고 던진다. 조용히 빼면
        그 정의의 문서만 비어 검토자가 지식이 없다고 오해한다.

        Raises:
            SelectionSpecError: 저장된 선택 규칙을 읽을 수 없을 때 던진다.
        """
        ...
