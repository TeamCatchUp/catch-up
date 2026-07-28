"""평가 원문 YAML을 NormalizedObservation으로 읽는다.

개발과 평가 전용이다. 운영 경로에서 쓰지 않는다.

운영에서는 `ObservationNormalizer`가 실제 SourceVersion을 정규화한다. 이
loader는 그 앞단이 아직 없는 동안 Extractor 계약을 실데이터 없이 시험하려고
둔 것이다. 따라서 SourceVersion을 만들지 않고 DB도 거치지 않는다.

원본은 Obsidian vault의 다음 문서이며, 마크다운을 직접 파싱하지 않도록
한 번 YAML로 옮겨 두었다.

    eval/2026-07-28-troubleshooting-llm-wiki-extraction-evaluation-source-candidates.md

`metadata_entities`는 항상 비어 있다. 원본이 이미 렌더링된 본문이라
고객이나 담당자가 구조화 필드가 아니라 텍스트 줄로만 남아 있기 때문이다.
결정론적 metadata 추출은 실제 connector payload를 다루는 정규화 adapter의
몫이며, 이 데이터셋으로는 검증하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash

DEFAULT_DATASET_PATH = (
    Path(__file__).parent / "data" / "llm_wiki_extraction_sources_v1.yaml"
)
NORMALIZER_ID = "evaluation.llm_wiki_extraction_dataset"


@dataclass(frozen=True, slots=True)
class ExtractionSource:
    """평가 원문 한 건과 그 정규화 결과를 묶는다.

    Attributes:
        key: 데이터셋 안에서 원문을 가리키는 번호를 나타낸다.
        document_id: 검색 projection이 쓰는 논리 문서 식별자를 보존한다.
        source_type: 원문이 유입된 source 종류를 나타낸다.
        cluster_id: 같은 주제로 묶인 원문 집합을 식별한다.
        observation: Extractor에 넣을 정규화 결과를 담는다.
    """

    key: str
    document_id: str
    source_type: str
    cluster_id: str
    observation: NormalizedObservation


def load_extraction_sources(
    path: Path | None = None,
) -> tuple[ExtractionSource, ...]:
    """평가 원문 데이터셋을 읽어 정규화 결과로 돌려준다."""
    dataset_path = path or DEFAULT_DATASET_PATH
    payload = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))

    version = str(payload["version"])
    cluster_of = {
        key: cluster["id"]
        for cluster in payload["clusters"]
        for key in cluster["documents"]
    }

    return tuple(
        ExtractionSource(
            key=document["key"],
            document_id=document["document_id"],
            source_type=document["source_type"],
            cluster_id=cluster_of[document["key"]],
            observation=NormalizedObservation(
                normalizer_id=NORMALIZER_ID,
                normalizer_version=version,
                observation_kind=ObservationKind.DOCUMENT,
                content=document["content"],
                content_hash=content_hash(document["content"]),
            ),
        )
        for document in payload["documents"]
    )
