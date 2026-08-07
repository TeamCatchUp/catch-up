/**
 * 검토 큐 diff 뷰 타입.
 *
 * WikiBlock은 [BE] blocks[] JSONB 원소의 mock 계약이고, 나머지는 전부 프론트가
 * computeBlockDiff로 계산해 만드는 값이라 백엔드 계약이 아니다(닫힌 union 허용).
 * 근거: docs/specs/2026-08-07-llm-wiki-diff-view-design.md §4
 */

/**
 * [BE] knowledge_mutation_proposals.blocks / 발행판 blocks의 원소.
 * 블록 고유 ID가 없어 페어링 키는 claimIds뿐이다(매칭 규칙은 백엔드 미문서화 — [SPEC] 가정).
 */
export interface WikiBlock {
  /** [BE] kind — claim_section·open_question 2종이 실재하나 목록이 흔들려 닫지 않는다 */
  kind: string;
  heading: string;
  /** 플레인 문자열 — 인라인 서식 없음(에디터 설계 §3) */
  body: string;
  /** [BE] claim_ids — 페어링 키 */
  claimIds: readonly string[];
  /** [SPEC] "수정된 이유" — 백엔드 필드 미확정, 계약 협상 대상 */
  reason?: string | null;
  /**
   * [SPEC] 삭제 제안 표식. proposed 배열에 tombstone으로 실린다.
   *
   * 삭제를 "proposed에서 빠짐"으로만 표현하면 사유를 실을 자리가 없다 — 삭제된 블록도
   * 사유를 갖는다는 계약(2026-08-07 결정)이라 명시 표현이 필요하다. 삭제될 원문은
   * 페어링된 base 블록에서 가져오므로 tombstone의 body는 비워도 된다.
   */
  removed?: boolean;
}

export type BlockChangeKind = 'added' | 'removed' | 'modified';

export interface DiffSegment {
  text: string;
  /** 단어 수준 변경 강조(진한 배경). modified 카드에서만 true가 나온다 */
  emphasized: boolean;
}

/** 호버 단위 = 줄. 블록 body의 줄바꿈으로 나뉜다 */
export interface DiffLine {
  segments: readonly DiffSegment[];
}

export interface BlockDiffEntry {
  id: string;
  kind: BlockChangeKind;
  /** 블록 heading. heading 변경 감지는 MVP 밖(스펙 §10 갭 기록) */
  title: string;
  before: readonly DiffLine[] | null; // added면 null
  after: readonly DiffLine[] | null; // removed면 null
  reason: string | null;
}
