/**
 * 검토 큐 diff 뷰 타입. WikiBlock 계열만 [BE] 계약이고,
 * 나머지는 computeBlockDiff가 만드는 프론트 값이라 닫힌 union을 쓴다.
 */

/** [BE] 블록 본문 한 줄의 근거 인용. citationVerified는 검증/대조 실패/근거 없음 3값이다 */
export interface BlockSource {
  claimId: string;
  statement: string;
  observedAt: string;
  citationVerified: boolean | null;
}

/** [BE] 다툼 블록이 나란히 보여 주는 후보. claimId가 판정에 실을 승자 식별자다 */
export interface BlockVariant {
  claimId: string;
  body: string;
  sources: readonly BlockSource[];
}

/** [BE] 블록에 이미 내려진 결정. blockContentHash는 그 결정이 어떤 본문을 보고 내려졌는지의 지문이다 */
export interface BlockVerdict {
  proposalId: string;
  blockIndex: number;
  blockContentHash: string;
  verdict: string;
  rejectionReason: string | null;
  chosenWinnerClaimId: string | null;
  reviewer: string;
  reviewedAt: string;
}

/**
 * [BE] 제안·발행판 blocks[]의 원소.
 * 블록 고유 ID가 없어 base↔proposed 페어링 키는 claimIds뿐이다 — 매칭 규칙은 백엔드 미확정.
 */
export interface WikiBlock {
  /** [BE] 목록에서의 자리. 블록 판정 요청 경로에 그대로 실린다 */
  blockIndex: number;
  /** [BE] 블록 종류. 목록이 흔들려 닫지 않는다 */
  kind: string;
  heading: string;
  /** 플레인 문자열 — 인라인 서식 없음 */
  body: string;
  /** [BE] 페어링 키이자 블록 단위 Read Set */
  claimIds: readonly string[];
  proposalIds: readonly string[];
  ontologyVersion: string | null;
  /** [BE] 현재 본문의 지문. 판정 요청에 필수인 낙관적 잠금 키다 */
  blockContentHash: string;
  /** [BE] 근거 인용. 다툼 블록은 여기를 비우고 variants에만 싣는다 — 정본이 두 자리에 나오면 안 된다 */
  sources: readonly BlockSource[];
  /** [BE] 다툼 블록에서만 값이 있다. null은 "다툼 아님"이고 빈 배열과 뜻이 다르다 */
  variants: readonly BlockVariant[] | null;
  /** [BE] 저장된 결정. 미판정이면 null */
  verdict: BlockVerdict | null;
  /** [SPEC] "수정된 이유" — 백엔드 대응 컬럼 없음, 계약 협상 대상 */
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
   * [BE] 블록 판정 요청에 필요한 두 값. proposed 쪽 블록에서 온다.
   * tombstone 없이 빠진 블록은 proposed에 자리가 없어 둘 다 null이고, 판정할 경로도 없다.
   */
  blockIndex: number | null;
  blockContentHash: string | null;
  /**
   * [SPEC] 반려 처리된 블록. 헤더의 액션 버튼이 "반려됨" 배지로 대체된다.
   * 승인됨 배지는 시안에 없어 대응 값을 만들지 않는다 — 그래서 불리언이다.
   */
  rejected?: boolean;
}
