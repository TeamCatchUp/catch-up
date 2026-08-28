from __future__ import annotations

from catchup.evaluation.llm_wiki_extraction_dataset import load_extraction_sources
from catchup.knowledge_maintenance.domain.observation import ObservationKind


def test_document_is_loaded_as_normalized_observation() -> None:
    sources = load_extraction_sources()

    first = next(source for source in sources if source.key == "01")

    assert first.document_id == "jira:issue:CATDEV-382"
    assert first.source_type == "jira"
    assert first.cluster_id == "slack-ingestion"
    assert first.observation.observation_kind == ObservationKind.DOCUMENT
    assert first.observation.content.startswith("[CATDEV-382]")
    assert first.observation.content_hash is not None
