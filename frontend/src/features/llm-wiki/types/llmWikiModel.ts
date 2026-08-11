/**
 * LLM Wiki 도메인 타입. 백엔드 제품 API가 없어 전부 mock 계약이다.
 * [BE]는 ERD에 실재하는 컬럼, [SPEC]은 명세에만 있고 백엔드 대응이 없는 값이다.
 */

// [BE] 제안 판정 — DB CHECK로 닫힌 집합
export type ChangeProposalStatus = 'pending' | 'approved' | 'rejected' | 'abandoned';

// [BE] 검토 큐 3종. 명세는 6유형이라 목록이 흔들린다 — 닫힌 enum 금지
export type KnownReviewItemType = 'publish' | 'merge' | 'contradiction';
export type ReviewItemType = KnownReviewItemType | (string & {});

/**
 * [SPEC] 문서 상태. 백엔드에 대응 필드가 없고, 큐 행의 `status`(제안 판정)와 다른 축이다.
 * 확정된 셋 밖은 미정이라 열어둔다.
 */
export type KnownDocumentStatus = 'reviewed' | 'pending_review' | 'needs_review';
export type DocumentStatus = KnownDocumentStatus | (string & {});

// breadcrumb 종류. 아이콘이 정의된 것은 채널·폴더 2종뿐이라 나머지는 열어둔다
export type KnownBreadcrumbKind = 'channel' | 'folder';
export type BreadcrumbKind = KnownBreadcrumbKind | (string & {});

/** [SPEC] 채널 > 폴더 경로의 한 마디. 종류마다 아이콘이 갈려서 문자열로 뭉갤 수 없다 */
export interface DocumentBreadcrumb {
  kind: BreadcrumbKind;
  label: string;
}

/**
 * 대시보드 문서 표의 행 계약.
 * 폴더·채널 화면의 행은 열 구성이 달라 별도 계약이다 — vocCount·customerCount는 여기 두지 않는다.
 */
export interface DocumentRowData {
  id: string;
  /** [BE] 문서 제목 */
  title: string;
  /** [SPEC] 채널 > 폴더 경로. 백엔드에 채널·폴더 개념 없음 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  status: DocumentStatus;
  /** 에러 아이콘 행 — 배지와의 공존 규칙은 미정이라 시각만 존재 */
  hasConflictIcon: boolean;
  /** [SPEC] 태그 목록. 행에는 첫 1개만 칩으로 보이고 나머지는 "+N"으로 접힌다 */
  tags: readonly string[];
  /** [SPEC] 최근 활동 표시 문자열 (예: "3시간 전") */
  lastActivityLabel: string;
}

export interface ReviewQueueItemData {
  id: string;
  type: ReviewItemType;
  /** [BE] 행 제목 */
  title: string;
  authorName: string;
  authorProfileImageUrl: string | null;
  /** 대기 기간 표시 문자열 (예: "15시간 전") */
  waitingLabel: string;
  /**
   * [BE] 추출 신뢰도(0~1). 명세의 "연결 신뢰도"와 다른 값이다.
   * 행 UI에는 표시하지 않는다 — 계약 보존용.
   */
  confidence: number;
  status: ChangeProposalStatus;
  /** [BE] rejected면 필수 (DB CHECK) */
  rejectionReason: string | null;
  /** [BE] stale 판정 기준 revision */
  baseRevisionId: string;
  /** 충돌(에러 아이콘) 행 — 상단 고정 여부는 미정 */
  hasConflictIcon: boolean;
}

export interface ReviewStatCardData {
  id: string;
  /** 검토 대기 · 미해결 충돌 · 태그 미분류 · 장기 미변경 문서 */
  label: string;
  count: number;
}

/**
 * [SPEC] 태그. 백엔드 스키마에 없고, 계층 없이 평평한 목록이 유일한 단위다.
 * documentCount는 계약 보존용이라 TagNavigationList가 렌더하지 않는다.
 */
export interface TagItem {
  id: string;
  name: string;
  documentCount: number;
}
