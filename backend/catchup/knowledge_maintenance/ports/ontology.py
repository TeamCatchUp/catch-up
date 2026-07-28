from __future__ import annotations

from typing import Protocol

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary


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

        같은 버전을 두 번 저장하려 하면 기존 것을 그대로 쓴다. 어휘는 그
        버전에서 확정된 값이므로 덮어쓰지 않는다.
        """
        ...

    def list_versions(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> tuple[str, ...]: ...
