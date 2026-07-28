from __future__ import annotations

from typing import Protocol

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary


class OntologySnapshotConflict(ValueError):
    """같은 버전 이름에 다른 어휘를 담으려 했음을 알린다.

    조용히 기존 값을 돌려주면 실행이 가리키는 스냅샷과 실제로 LLM에 넣은
    어휘가 달라진다. 스냅샷을 남긴 목적이 감사인데 그 기록이 거짓이 된다.
    """


class OntologyRepository(Protocol):
    """추출이 따른 어휘 목록의 영속성을 정의한다.

    버전 문자열만 남기고 목록을 버리면 나중에 어휘를 통합할 때 과거 후보가
    어떤 규칙 아래 만들어졌는지 되짚지 못한다. 그래서 스냅샷을 행으로 남긴다.

    어휘가 없던 시점도 빈 목록으로 남긴다. 그 사실 자체가 기록이다.
    """

    def get(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        version: str,
    ) -> ExtractionVocabulary | None: ...

    def ensure(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        vocabulary: ExtractionVocabulary,
    ) -> ExtractionVocabulary:
        """스냅샷을 남기거나 이미 있는 것을 돌려준다.

        어휘는 그 버전에서 확정된 값이므로 덮어쓰지 않는다. 다만 같은 이름에
        다른 내용을 넣으려 하면 `OntologySnapshotConflict`를 던진다. 덮어쓰지
        않는 것과 충돌을 삼키는 것은 다르다.
        """
        ...

    def list_versions(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> tuple[str, ...]: ...
