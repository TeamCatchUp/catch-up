/**
 * 검토 큐 diff 뷰 타입. WikiBlock만 [BE] 계약이고,
 * 나머지는 computeBlockDiff가 만드는 프론트 값이라 닫힌 union을 쓴다.
 */

/**
 * [BE] 제안·발행판 blocks[]의 원소.
 * 블록 고유 ID가 없어 페어링 키는 claimIds뿐이다 — 매칭 규칙은 백엔드 미확정.
 */
export interface WikiBlock {
  /** [BE] 블록 종류. 목록이 흔들려 닫지 않는다 */
  kind: string;
  heading: string;
  /** 플레인 문자열 — 인라인 서식 없음 */
  body: string;
  /** [BE] 페어링 키 */
  claimIds: readonly string[];
  /** [SPEC] "수정된 이유" — 백엔드 필드 미확정, 계약 협상 대상 */
  reason?: string | null;
  /**
   * [SPEC] 삭제 제안 표식. proposed 배열에 tombstone으로 실린다 — 삭제된 블록도 사유를 갖기 때문이다.
   * 원문은 페어링된 base 블록에서 가져오므로 tombstone의 body는 비워도 된다.
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
  /** 블록 heading. heading 변경 감지는 범위 밖 */
  title: string;
  before: readonly DiffLine[] | null; // added면 null
  after: readonly DiffLine[] | null; // removed면 null
  reason: string | null;
  /**
   * [SPEC] 반려 처리된 블록. 헤더의 액션 버튼이 "반려됨" 배지로 대체된다.
   * 승인됨 배지는 시안에 없어 대응 값을 만들지 않는다 — 그래서 불리언이다.
   */
  rejected?: boolean;
}
