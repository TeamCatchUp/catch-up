/**
 * LLM Wiki 도메인 타입. [BE]는 백엔드 스키마에 실재하는 값(knowledge_review·wiki),
 * [SPEC]은 명세에만 있고 백엔드 대응이 없는 값이다.
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

/** [BE] 채널 > 폴더 경로의 한 마디. 종류마다 아이콘이 갈려서 문자열로 뭉갤 수 없다 */
export interface DocumentBreadcrumb {
  kind: BreadcrumbKind;
  label: string;
}

/** [BE] 채널. 식별자는 UUID 문자열 — 파싱 없이 경로에 그대로 싣는 계약이다 */
export interface WikiChannel {
  id: string;
  name: string;
  workspaceId: number;
}

/** [BE] 폴더. 채널 바로 아래 한 겹뿐이다(depth 1 고정) — 상위 폴더 필드가 계약에 없다 */
export interface WikiFolder {
  id: string;
  name: string;
  channelId: string;
}

/**
 * [BE] 채널 목록 한 줄. isAdmin·documentCount·folders가 동봉된다 —
 * 관리 버튼 노출 판정을 목록과 같은 왕복에서 끝내기 위한 계약이다.
 */
export interface WikiChannelListItem extends WikiChannel {
  isAdmin: boolean;
  documentCount: number;
  folders: readonly WikiFolder[];
}

/**
 * 대시보드 문서 표의 행 계약.
 * 폴더·채널 화면의 행은 열 구성이 달라 별도 계약이다 — vocCount·customerCount는 여기 두지 않는다.
 */
export interface DocumentRowData {
  id: string;
  /** [BE] 문서 제목 */
  title: string;
  /** [BE] 채널 > 폴더 경로. 실물은 WikiChannel·WikiFolder — 경로 조립은 프론트 몫 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  status: DocumentStatus;
  /**
   * [BE] 담당자 표시명. null은 미지정이다 — 지정·해제 API가 실물이라 실제로 발생하는 상태다.
   * 목록 응답에 이름·이미지는 미동봉(협상 대상).
   */
  ownerName: string | null;
  ownerProfileImageUrl: string | null;
  /** [BE] 생성 시각(ISO). 생성일 필터가 대조하는 값이다 */
  createdAt: string;
  /**
   * [BE] 최근 활동 시각(ISO). 정렬 기준이다 — 표시 문자열은 "3시간 전"처럼 상대 표기라 정렬에 쓸 수 없다.
   */
  lastActivityAt: string;
  /** [SPEC] 최근 활동 표시 문자열 (예: "3시간 전", "2024.12.12") */
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
  /** 검토 대기 · 내 담당 · 담당자 미지정 */
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
