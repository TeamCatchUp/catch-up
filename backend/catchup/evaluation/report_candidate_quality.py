"""저장된 knowledge candidate의 품질을 수치로 요약한다.

라벨 없이 DB만으로 계산할 수 있는 지표를 한 벌로 묶는다. 손 판독
기준선([[2026-07-28-llm-wiki-extraction-quality-baseline]])이 정밀도를
말한다면, 이 리포트는 Resolution 난이도와 어휘 발산을 말한다.

reset → ingestion → extraction 루프 뒤에 돌려 실행 간 변화를 비교하고,
Resolution이 생기면 합치기 전후의 계기판으로 쓴다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.report_candidate_quality
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy import text

from catchup.configs.config import settings

SCALE_SQL = """
SELECT
  (SELECT count(*) FROM knowledge_extraction_runs
    WHERE workspace_id = :ws AND status = 'succeeded') AS runs_ok,
  (SELECT count(*) FROM knowledge_extraction_runs
    WHERE workspace_id = :ws AND status = 'failed') AS runs_failed,
  (SELECT count(*) FROM knowledge_entity_candidates
    WHERE workspace_id = :ws
      AND extraction_method = 'deterministic') AS entities_det,
  (SELECT count(*) FROM knowledge_entity_candidates
    WHERE workspace_id = :ws AND extraction_method = 'llm') AS entities_llm,
  (SELECT count(*) FROM knowledge_claim_candidates
    WHERE workspace_id = :ws) AS claims,
  (SELECT count(*) FROM knowledge_relation_assertion_candidates
    WHERE workspace_id = :ws) AS relations
"""

ENTITY_SPLIT_SQL = """
WITH names AS (
  SELECT lower(trim(proposed_name)) AS name,
         count(DISTINCT proposed_type) AS type_kinds,
         count(DISTINCT extraction_run_id) AS runs
  FROM knowledge_entity_candidates
  WHERE workspace_id = :ws AND extraction_method = 'llm'
  GROUP BY 1
)
SELECT count(*) AS distinct_names,
       count(*) FILTER (WHERE runs > 1) AS multi_run_names,
       count(*) FILTER (WHERE runs > 1 AND type_kinds > 1) AS split_names
FROM names
"""

ENTITY_SPLIT_LIST_SQL = """
SELECT lower(trim(proposed_name)) AS name,
       count(DISTINCT proposed_type) AS types,
       array_agg(DISTINCT proposed_type) AS type_list
FROM knowledge_entity_candidates
WHERE workspace_id = :ws AND extraction_method = 'llm'
GROUP BY 1
HAVING count(DISTINCT extraction_run_id) > 1
   AND count(DISTINCT proposed_type) > 1
ORDER BY 2 DESC
"""

ENTITY_COMPRESSION_SQL = """
SELECT count(*) AS rows,
       count(DISTINCT lower(trim(proposed_name))) AS names
FROM knowledge_entity_candidates
WHERE workspace_id = :ws
"""

CLAIM_SQL = """
SELECT
  (SELECT count(*) FROM knowledge_claim_candidates
    WHERE workspace_id = :ws) AS claims,
  (SELECT count(*) FROM (
     SELECT predicate FROM knowledge_claim_candidates
     WHERE workspace_id = :ws
     GROUP BY predicate
     HAVING count(DISTINCT value_type) > 1) t
  ) AS mixed_value_type_predicates,
  (SELECT count(*)
   FROM knowledge_claim_candidates c
   JOIN knowledge_entity_candidates e
     ON c.subject_entity_candidate_id = e.id
   WHERE c.workspace_id = :ws
     AND trim(both '"' from c.value::text) = e.proposed_name
  ) AS self_referential,
  (SELECT count(*) FROM knowledge_claim_candidates
    WHERE workspace_id = :ws
      AND (valid_from IS NOT NULL OR valid_to IS NOT NULL)
  ) AS with_time_axis
"""

CONTRADICTION_SQL = """
SELECT e.proposed_name AS subject,
       c.predicate,
       count(DISTINCT c.value_hash) AS distinct_values
FROM knowledge_claim_candidates c
JOIN knowledge_entity_candidates e
  ON c.subject_entity_candidate_id = e.id
WHERE c.workspace_id = :ws
GROUP BY 1, 2
HAVING count(DISTINCT c.value_hash) > 1
ORDER BY 3 DESC
"""

VOCAB_SQL = """
SELECT
  (SELECT count(DISTINCT predicate) FROM knowledge_claim_candidates
    WHERE workspace_id = :ws) AS predicates,
  (SELECT count(*) FROM (
     SELECT predicate FROM knowledge_claim_candidates
     WHERE workspace_id = :ws GROUP BY 1 HAVING count(*) = 1) t
  ) AS single_use_predicates,
  (SELECT count(DISTINCT relation_type)
   FROM knowledge_relation_assertion_candidates
   WHERE workspace_id = :ws) AS relation_types,
  (SELECT count(*) FROM (
     SELECT relation_type FROM knowledge_relation_assertion_candidates
     WHERE workspace_id = :ws GROUP BY 1 HAVING count(*) = 1) t
  ) AS single_use_rel_types,
  (SELECT round(
     100.0 * count(*) FILTER (
       WHERE se.extraction_method = 'deterministic'
          OR te.extraction_method = 'deterministic') / nullif(count(*), 0),
     1)
   FROM knowledge_relation_assertion_candidates r
   LEFT JOIN knowledge_entity_candidates se
     ON r.source_entity_candidate_id = se.id
   LEFT JOIN knowledge_entity_candidates te
     ON r.target_entity_candidate_id = te.id
   WHERE r.workspace_id = :ws
  ) AS metadata_endpoint_pct
"""

CITATION_SQL = """
SELECT count(*) FILTER (WHERE locator != '{}'::jsonb) AS located,
       count(*) FILTER (WHERE locator = '{}'::jsonb) AS demoted
FROM knowledge_candidate_evidence_links
WHERE workspace_id = :ws AND claim_candidate_id IS NOT NULL
"""

RESOLUTION_SQL = """
SELECT
  (SELECT count(*) FROM knowledge_nodes
    WHERE workspace_id = :ws AND node_kind = 'entity') AS canonical_entities,
  (SELECT count(*) FROM knowledge_entity_candidates
    WHERE workspace_id = :ws
      AND resolution_status = 'accepted') AS accepted,
  (SELECT count(*) FROM knowledge_entity_candidates
    WHERE workspace_id = :ws
      AND resolution_status = 'merged') AS merged,
  (SELECT count(*) FROM knowledge_entity_candidates
    WHERE workspace_id = :ws
      AND resolution_status = 'pending') AS still_pending,
  (SELECT count(*) FROM knowledge_mutation_proposals
    WHERE workspace_id = :ws AND status = 'pending') AS pending_proposals,
  (SELECT count(*) FROM knowledge_node_aliases
    WHERE workspace_id = :ws) AS aliases
"""


def _pct(part: int, whole: int) -> str:
    """비율을 표시용 문자열로 만든다."""
    if not whole:
        return "-"
    return f"{100.0 * part / whole:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    args = parser.parse_args()
    params = {"ws": args.workspace_id}

    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.connect() as conn:
        scale = conn.execute(text(SCALE_SQL), params).mappings().one()
        split = conn.execute(text(ENTITY_SPLIT_SQL), params).mappings().one()
        split_list = (
            conn.execute(text(ENTITY_SPLIT_LIST_SQL), params).mappings().all()
        )
        compression = (
            conn.execute(text(ENTITY_COMPRESSION_SQL), params).mappings().one()
        )
        claim = conn.execute(text(CLAIM_SQL), params).mappings().one()
        contradictions = (
            conn.execute(text(CONTRADICTION_SQL), params).mappings().all()
        )
        vocab = conn.execute(text(VOCAB_SQL), params).mappings().one()
        citation = conn.execute(text(CITATION_SQL), params).mappings().one()
        resolution = (
            conn.execute(text(RESOLUTION_SQL), params).mappings().one()
        )
    engine.dispose()

    print("=== 규모 ===")
    print(
        f"  run 성공 {scale['runs_ok']} · 실패 {scale['runs_failed']}"
        f"  | entity det {scale['entities_det']} + llm {scale['entities_llm']}"
        f"  | claim {scale['claims']}  | relation {scale['relations']}"
    )

    print("\n=== Entity — Resolution 난이도 ===")
    print(
        f"  type 분열: 다회 등장 이름 {split['multi_run_names']}개 중 "
        f"{split['split_names']}개 분열 "
        f"({_pct(split['split_names'], split['multi_run_names'])})"
    )
    for row in split_list:
        print(
            f"    {row['name']}: {row['types']}종 "
            f"{list(row['type_list'])}"
        )
    print(
        f"  압축 잠재율: {compression['rows']}행 → "
        f"고유 이름 {compression['names']}개 "
        f"({compression['rows'] / max(compression['names'], 1):.2f}배)"
    )

    print("\n=== Claim — 품질 프록시 ===")
    print(
        f"  value_type 흔들리는 predicate "
        f"{claim['mixed_value_type_predicates']}/{vocab['predicates']}"
        f"  | 자기참조 {claim['self_referential']}"
        f"  | 시간축 채움 {claim['with_time_axis']}/{claim['claims']}"
    )
    print(f"  모순 후보 쌍 (같은 subject+predicate, 다른 값): "
          f"{len(contradictions)}")
    for row in contradictions:
        print(
            f"    {row['subject']} · {row['predicate']} — "
            f"값 {row['distinct_values']}종"
        )

    print("\n=== 어휘 발산 ===")
    print(
        f"  predicate {vocab['predicates']}종 "
        f"(1회성 {vocab['single_use_predicates']}, "
        f"{_pct(vocab['single_use_predicates'], vocab['predicates'])})"
        f"  | relation_type {vocab['relation_types']}종 "
        f"(1회성 {vocab['single_use_rel_types']}, "
        f"{_pct(vocab['single_use_rel_types'], vocab['relation_types'])})"
    )
    print(f"  metadata 끝점 비율: {vocab['metadata_endpoint_pct']}%")

    print("\n=== 인용 검증 ===")
    checked = citation["located"] + citation["demoted"]
    print(
        f"  위치 확정 {citation['located']} · 강등 {citation['demoted']}"
        f" (강등률 {_pct(citation['demoted'], checked)})"
    )

    print("\n=== Resolution ===")
    resolved = resolution["accepted"] + resolution["merged"]
    ratio = (
        f"{resolved / resolution['canonical_entities']:.2f}배"
        if resolution["canonical_entities"]
        else "-"
    )
    print(
        f"  canonical entity {resolution['canonical_entities']}"
        f"  | 후보 accepted {resolution['accepted']}"
        f" · merged {resolution['merged']}"
        f" · pending {resolution['still_pending']}"
    )
    print(
        f"  실측 압축률 {ratio} (해소 후보 {resolved} ÷ canonical)"
        f"  | pending proposal {resolution['pending_proposals']}"
        f"  | alias {resolution['aliases']}"
    )


if __name__ == "__main__":
    main()
