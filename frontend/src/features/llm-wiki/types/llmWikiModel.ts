/**
 * LLM Wiki 도메인 타입.
 *
 * 백엔드 제품 API가 아직 없어 전부 mock 계약이다. 필드 구분:
 * - [BE] : ERD(knowledge_* 테이블)에 실재하는 컬럼 — 이름·의미를 백엔드 용어에 맞춘다
 * - [SPEC]: MVP 명세에만 있고 백엔드 대응이 없는 값 — API 계약 협상 대상
 * 근거: docs/specs/2026-08-05-llm-wiki-erd-design.md, docs/specs/2026-08-06-llm-wiki-storybook-batch1-design.md §3
 */

// [BE] knowledge_artifact_change_proposals.status — DB CHECK로 닫힌 집합
export type ChangeProposalStatus = 'pending' | 'approved' | 'rejected' | 'abandoned';

// [BE] 백엔드 검토 큐 3종. 명세는 6유형이라 목록이 아직 흔들린다 — 닫힌 enum 금지
export type KnownReviewItemType = 'publish' | 'merge' | 'contradiction';
export type ReviewItemType = KnownReviewItemType | (string & {});

// 디자인 확정 배지는 "검토 완료" 1종뿐 — 나머지 상태 표기는 미정이라 열어둔다
export type KnownDocumentStatus = 'reviewed';
export type DocumentStatus = KnownDocumentStatus | (string & {});

export interface DocumentRowData {
  id: string;
  /** [BE] knowledge_artifacts.title */
  title: string;
  /** [SPEC] 채널 > 폴더 경로. 백엔드에 채널·폴더 개념 없음 */
  breadcrumbs: readonly string[];
  status: DocumentStatus;
  /** 에러 아이콘 행 — 배지와의 공존 규칙 UNKNOWN(감사) 상태로 시각만 존재 */
  hasConflictIcon: boolean;
  /** [SPEC] 연결 VOC 수 — 집계 API 협상 대상 */
  vocCount: number;
  /** [SPEC] 고객사 수 — 집계 API 협상 대상 */
  customerCount: number;
  /** [SPEC] 최근 활동 표시 문자열 (예: "3시간 전") */
  lastActivityLabel: string;
}

export interface ReviewQueueItemData {
  id: string;
  type: ReviewItemType;
  /** [BE] mutation_proposals.summary 계열 — 행 제목 */
  title: string;
  authorName: string;
  authorProfileImageUrl: string | null;
  /** 대기 기간 표시 문자열 (예: "15시간 전") */
  waitingLabel: string;
  /**
   * [BE] 추출 신뢰도(knowledge_*_candidates.confidence, 0~1).
   * 명세의 "연결 신뢰도"와 다른 값이다 — 연결 신뢰도는 백엔드에 없다.
   * 감사 판정상 행 UI에는 표시하지 않는다(MISSING). 계약 보존용으로만 담는다.
   */
  confidence: number;
  status: ChangeProposalStatus;
  /** [BE] rejected면 필수 (DB CHECK) */
  rejectionReason: string | null;
  /** [BE] stale 판정 기준 revision */
  baseRevisionId: string;
  /** 충돌(에러 아이콘) 행 — 상단 고정 규칙은 UNKNOWN */
  hasConflictIcon: boolean;
}

export interface ReviewStatCardData {
  id: string;
  /** Figma 확정 4종: 검토 대기 · 미해결 충돌 · 태그 미분류 · 장기 미변경 문서 */
  label: string;
  count: number;
}

export interface TagItem {
  id: string;
  name: string;
  documentCount: number;
}

/** [SPEC] 태그는 전부 명세 유래 — 백엔드 스키마에 없음 */
export interface TagCategory {
  id: string;
  name: string;
  tags: readonly TagItem[];
}
