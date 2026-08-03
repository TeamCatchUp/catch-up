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
  ) AS with_time_axis,
  (SELECT count(*) FROM knowledge_claim_candidates
    WHERE workspace_id = :ws
      AND valid_from IS NOT NULL
  ) AS with_valid_from
"""

# valid_to를 무엇으로 채웠는지는 스키마 컬럼이 아니라 결정 metadata에
# 남는다. decision_time이 많다면 사건 시각을 못 얻고 있다는 뜻이다.
VALID_TO_SOURCE_SQL = """
SELECT resolver_metadata->'decision'->>'valid_to_source' AS source,
       count(*) AS decisions
FROM knowledge_mutation_proposals
WHERE workspace_id = :ws
  AND proposal_kind = 'contradiction'
  AND status IN ('approved', 'applied')
  AND resolver_metadata->'decision' ? 'valid_to_source'
GROUP BY 1
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


ONTOLOGY_ID = "catchup.knowledge_candidates"

# 사전 항목은 스냅샷의 predicates 컬럼 안에 객체로 들어 있다. 이름 목록만
# 담긴 v1 스냅샷이면 `->`가 NULL을 돌려주고 이 CTE는 0행이 된다.
DICTIONARY_ENTRIES_CTE = """
WITH entries AS (
  SELECT e->>'name' AS name,
         e->>'value_type' AS value_type,
         ARRAY(SELECT jsonb_array_elements_text(e->'domain')) AS domain
  FROM knowledge_ontology_snapshots s
  CROSS JOIN LATERAL jsonb_array_elements(
    s.predicates->'predicate_entries') AS e
  WHERE s.workspace_id = :ws
    AND s.ontology_id = :ontology
    AND s.version = :version
)
"""

DICTIONARY_COVERAGE_SQL = (
    DICTIONARY_ENTRIES_CTE
    + """,
used AS (
  SELECT predicate, count(*) AS uses
  FROM knowledge_claim_candidates
  WHERE workspace_id = :ws
  GROUP BY 1
)
SELECT (SELECT count(*) FROM entries) AS dictionary_size,
       count(*) AS used_predicates,
       count(*) FILTER (WHERE e.name IS NOT NULL) AS listed_predicates,
       coalesce(sum(u.uses), 0)::bigint AS claims,
       coalesce(
         sum(u.uses) FILTER (WHERE e.name IS NOT NULL), 0
       )::bigint AS listed_claims
FROM used u
LEFT JOIN entries e ON e.name = u.predicate
"""
)

DICTIONARY_UNLISTED_SQL = (
    DICTIONARY_ENTRIES_CTE
    + """,
used AS (
  SELECT predicate, count(*) AS uses
  FROM knowledge_claim_candidates
  WHERE workspace_id = :ws
  GROUP BY 1
)
SELECT u.predicate, u.uses
FROM used u
LEFT JOIN entries e ON e.name = u.predicate
WHERE e.name IS NULL
ORDER BY u.uses DESC, u.predicate
"""
)

# 사전이 domain을 비워 둔 predicate는 어디에 붙어도 되므로 세지 않는다.
OFF_DOMAIN_SQL = (
    DICTIONARY_ENTRIES_CTE
    + """,
subjects AS (
  SELECT c.predicate,
         coalesce(ec.proposed_type, n.entity_type) AS subject_type
  FROM knowledge_claim_candidates c
  LEFT JOIN knowledge_entity_candidates ec
    ON c.subject_entity_candidate_id = ec.id
  LEFT JOIN knowledge_nodes n
    ON c.subject_node_id = n.id
  WHERE c.workspace_id = :ws
)
SELECT count(*) AS checkable,
       count(*) FILTER (
         WHERE s.subject_type IS NULL
            OR NOT (s.subject_type = ANY(e.domain))
       ) AS off_domain
FROM subjects s
JOIN entries e ON e.name = s.predicate
WHERE cardinality(e.domain) > 0
"""
)

OFF_DOMAIN_LIST_SQL = (
    DICTIONARY_ENTRIES_CTE
    + """,
subjects AS (
  SELECT c.predicate,
         coalesce(ec.proposed_type, n.entity_type) AS subject_type
  FROM knowledge_claim_candidates c
  LEFT JOIN knowledge_entity_candidates ec
    ON c.subject_entity_candidate_id = ec.id
  LEFT JOIN knowledge_nodes n
    ON c.subject_node_id = n.id
  WHERE c.workspace_id = :ws
)
SELECT s.predicate,
       coalesce(s.subject_type, '(불명)') AS subject_type,
       e.domain AS declared_domain,
       count(*) AS claims
FROM subjects s
JOIN entries e ON e.name = s.predicate
WHERE cardinality(e.domain) > 0
  AND (s.subject_type IS NULL OR NOT (s.subject_type = ANY(e.domain)))
GROUP BY 1, 2, 3
ORDER BY 4 DESC, 1
"""
)

CONFLICT_PROPOSAL_SQL = """
WITH members AS (
  SELECT p.id,
         p.resolver_metadata->>'predicate' AS predicate,
         v->>'normalized' AS normalized
  FROM knowledge_mutation_proposals p
  CROSS JOIN LATERAL jsonb_array_elements(
    p.resolver_metadata->'values') AS v
  WHERE p.workspace_id = :ws
    AND p.proposal_kind = 'contradiction'
    AND p.status = 'pending'
),
per_proposal AS (
  SELECT id,
         predicate,
         count(*) AS claims,
         count(DISTINCT normalized) AS distinct_values
  FROM members
  GROUP BY 1, 2
)
SELECT count(*) AS proposals,
       coalesce(sum(claims), 0)::bigint AS member_claims,
       coalesce(sum(claims - distinct_values), 0)::bigint AS duplicates
FROM per_proposal
"""

CONFLICT_PROPOSAL_LIST_SQL = """
SELECT p.resolver_metadata->>'predicate' AS predicate,
       p.resolver_metadata->>'subject_key' AS subject_key,
       jsonb_array_length(p.resolver_metadata->'values') AS claims,
       (SELECT count(DISTINCT v->>'normalized')
        FROM jsonb_array_elements(p.resolver_metadata->'values') AS v
       ) AS distinct_values
FROM knowledge_mutation_proposals p
WHERE p.workspace_id = :ws
  AND p.proposal_kind = 'contradiction'
  AND p.status = 'pending'
ORDER BY 1, 2
"""


def _pct(part: int, whole: int) -> str:
    """비율을 표시용 문자열로 만든다."""
    if not whole:
        return "-"
    return f"{100.0 * part / whole:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--ontology-version",
        default="2",
        help="사전 섹션이 기준으로 삼을 어휘 스냅샷 버전을 정한다.",
    )
    args = parser.parse_args()
    params = {"ws": args.workspace_id}
    dict_params = {
        "ws": args.workspace_id,
        "ontology": ONTOLOGY_ID,
        "version": args.ontology_version,
    }

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
        valid_to_sources = (
            conn.execute(text(VALID_TO_SOURCE_SQL), params).mappings().all()
        )
        contradictions = (
            conn.execute(text(CONTRADICTION_SQL), params).mappings().all()
        )
        vocab = conn.execute(text(VOCAB_SQL), params).mappings().one()
        citation = conn.execute(text(CITATION_SQL), params).mappings().one()
        resolution = (
            conn.execute(text(RESOLUTION_SQL), params).mappings().one()
        )
        coverage = (
            conn.execute(text(DICTIONARY_COVERAGE_SQL), dict_params)
            .mappings()
            .one()
        )
        unlisted = (
            conn.execute(text(DICTIONARY_UNLISTED_SQL), dict_params)
            .mappings()
            .all()
        )
        off_domain = (
            conn.execute(text(OFF_DOMAIN_SQL), dict_params).mappings().one()
        )
        off_domain_list = (
            conn.execute(text(OFF_DOMAIN_LIST_SQL), dict_params)
            .mappings()
            .all()
        )
        conflict = (
            conn.execute(text(CONFLICT_PROPOSAL_SQL), params).mappings().one()
        )
        conflict_list = (
            conn.execute(text(CONFLICT_PROPOSAL_LIST_SQL), params)
            .mappings()
            .all()
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
        f"  | valid_from 채움률 {claim['with_valid_from']}/{claim['claims']}"
        f" ({_pct(claim['with_valid_from'], claim['claims'])})"
    )
    print(f"  모순 후보 쌍 (같은 subject+predicate, 다른 값): "
          f"{len(contradictions)}")
    for row in contradictions:
        print(
            f"    {row['subject']} · {row['predicate']} — "
            f"값 {row['distinct_values']}종"
        )

    print("\n=== 시간축 품질 ===")
    by_source = {row["source"]: row["decisions"] for row in valid_to_sources}
    if not by_source:
        print("  valid_to fallback 사용률 — 결정 없음")
    else:
        decided = sum(by_source.values())
        decision_time = by_source.get("decision_time", 0)
        print(
            f"  valid_to fallback 사용률 — "
            f"decision_time {decision_time}"
            f" / winner_valid_from {by_source.get('winner_valid_from', 0)}"
            f" (fallback {_pct(decision_time, decided)})"
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

    print(f"\n=== 사전 (v{args.ontology_version}) ===")
    if not coverage["dictionary_size"]:
        print(
            f"  스냅샷 {ONTOLOGY_ID} v{args.ontology_version}에 predicate "
            f"사전 항목이 없다. publish_vocabulary_snapshot을 먼저 돌린다."
        )
    else:
        listed_pct = _pct(
            coverage["listed_predicates"],
            coverage["used_predicates"],
        )
        print(
            f"  사전 {coverage['dictionary_size']}종"
            f"  | 사용된 predicate {coverage['used_predicates']}종 중 "
            f"등재 {coverage['listed_predicates']}종 ({listed_pct})"
        )
        print(
            f"  claim 기준 등재율 {coverage['listed_claims']}"
            f"/{coverage['claims']} "
            f"({_pct(coverage['listed_claims'], coverage['claims'])})"
        )
        for row in unlisted:
            print(f"    미등재 {row['predicate']} — claim {row['uses']}건")
        print(
            f"  off_domain (domain 선언된 predicate 한정): "
            f"{off_domain['off_domain']}/{off_domain['checkable']} "
            f"({_pct(off_domain['off_domain'], off_domain['checkable'])})"
            f" — 지표일 뿐 거부하지 않는다"
        )
        for row in off_domain_list:
            print(
                f"    {row['predicate']} ← {row['subject_type']} "
                f"(선언 {list(row['declared_domain'])}) "
                f"claim {row['claims']}건"
            )
    print(
        f"  contradiction proposal {conflict['proposals']}건"
        f"  | 묶인 claim {conflict['member_claims']}"
        f"  | 같은 값 중복 관찰(계류 모순) {conflict['duplicates']}"
    )
    for row in conflict_list:
        print(
            f"    {row['predicate']} · {row['subject_key']} — "
            f"claim {row['claims']}건 값 {row['distinct_values']}종"
        )


if __name__ == "__main__":
    main()
