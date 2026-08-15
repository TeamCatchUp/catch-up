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

    def lock_lineage(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> None:
        """한 `(workspace_id, ontology_id)` 계보의 발행을 직렬화한다.

        버전 이름은 기존 목록을 읽어 다음 번호를 세는 방식으로 정한다.
        두 트랜잭션이 동시에 읽으면 둘 다 같은 다음 번호를 세고, 뒤에
        커밋하는 쪽이 버전 UNIQUE 제약에 걸려 통째로 실패한다.

        잠금은 현재 트랜잭션이 끝날 때까지 유지되므로, 뒤에 온 쪽은
        앞의 커밋을 기다렸다가 최신 버전을 보고 다음 번호를 센다.
        발행할 뜻이 있으면 `list_versions`를 읽기 전에 먼저 부른다.
        """
        ...

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
