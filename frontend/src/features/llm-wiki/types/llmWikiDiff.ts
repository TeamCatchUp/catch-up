/**
 * 검토 큐 diff 뷰 타입. WikiBlock·BlockChange는 [BE] 계약이고,
 * DiffLine 계열은 표시용 파생이라 닫힌 union을 쓴다.
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
 * 블록 고유 ID가 없어 base↔proposed 짝짓기는 서버가 계산해 blockChanges로 내려준다.
 */
export interface WikiBlock {
  /** [BE] 목록에서의 자리. 블록 판정 요청 경로에 그대로 실린다 */
  blockIndex: number;
  /** [BE] 블록 종류. 목록이 흔들려 닫지 않는다 */
  kind: string;
  heading: string;
  /** 플레인 문자열 — 인라인 서식 없음 */
  body: string;
  /** [BE] 사람용 산문. 이쪽이 표시 정본이고 body는 값 표기다 — 없으면(옛 데이터) body로 폴백한다 */
  narrative: string | null;
  /** [BE] 블록 단위 Read Set */
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
  /** [BE] change_reason. 서버가 변경 종류·근거 증감에서 만든 요약 문구다 */
  reason?: string | null;
}

export type BlockChangeKind = 'added' | 'removed' | 'modified';

/**
 * [BE] 발행판과 견준 블록 하나의 변경. 바뀐 블록만 실리고 순서가 카드 순서다.
 * 자리가 두 축인 이유는 added·removed에 한쪽 짝이 없기 때문이다.
 */
export interface BlockChange {
  kind: BlockChangeKind;
  /** 변경안 blocks[] 안 자리. removed면 null */
  blockIndex: number | null;
  /** 발행판 baseBlocks[] 안 자리. added면 null */
  baseBlockIndex: number | null;
}

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
   * [BE] 블록 판정 요청에 필요한 두 값. 변경안 블록에서 온다.
   * removed 카드는 변경안에 자리가 없어 둘 다 null이고, 판정할 경로도 없다.
   */
  blockIndex: number | null;
  blockContentHash: string | null;
  /** [SPEC] 반려 처리된 블록. 헤더의 액션 버튼이 "반려됨" 배지로 대체된다 */
  rejected?: boolean;
  /** [BE] 그 반려에 검토자가 적은 사유. 반려된 카드에서만 값이 있다 */
  rejectionReason?: string | null;
  /** [SPEC] 승인 처리된 블록. 헤더의 액션 버튼이 "승인됨" 배지로 대체된다 */
  approved?: boolean;
}
