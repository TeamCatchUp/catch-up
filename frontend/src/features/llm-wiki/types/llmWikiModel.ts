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
 * 확정된 둘 밖은 미정이라 열어둔다.
 */
export type KnownDocumentStatus = 'reviewed' | 'pending_review';
export type DocumentStatus = KnownDocumentStatus | (string & {});

// breadcrumb 종류. 아이콘이 정의된 것은 채널·폴더 2종뿐이라 나머지는 열어둔다
export type KnownBreadcrumbKind = 'channel' | 'folder';
export type BreadcrumbKind = KnownBreadcrumbKind | (string & {});

/** [BE] 채널 > 폴더 경로의 한 마디. 종류마다 아이콘이 갈려서 문자열로 뭉갤 수 없다 */
export interface DocumentBreadcrumb {
  kind: BreadcrumbKind;
  label: string;
  /** 이동 대상 id. 이름만으로 조립되는 정적 마디는 비운다 — 그 마디는 눌러도 이동이 없다 */
  id?: string;
}

/**
 * [BE] 문서 담당자 한 명. 목록 응답의 owners[] 원소이고, 식별은 userId다 —
 * 동명이인이 있어 표시명으로 사람을 가를 수 없다.
 */
export interface DocumentOwner {
  userId: number;
  displayName: string;
  profileImageUrl: string | null;
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
  /** [BE] 폴더 생성 시각(ISO) */
  createdAt: string;
  /** [BE] 만든 사람. 컬럼이 생기기 전 폴더와 사용자 행이 사라진 폴더는 null이다 */
  createdBy: DocumentOwner | null;
  /** [BE] 폴더 안 문서가 마지막으로 움직인 시각(ISO). 문서가 없으면 null이다 */
  lastActivityAt: string | null;
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
   * [BE] 담당자 목록. 빈 배열은 미지정이다 — 지정·해제 API가 실물이라 실제로 발생하는 상태다.
   * 2인 이상 표시 시안이 없어 행은 첫 담당자만 렌더한다.
   */
  owners: readonly DocumentOwner[];
  /** [BE] 생성 시각(ISO). 생성일 필터가 대조하는 값이다 */
  createdAt: string;
  /**
   * [BE] 최근 활동 시각(ISO). 정렬 기준이다 — 표시 문자열은 "3시간 전"처럼 상대 표기라 정렬에 쓸 수 없다.
   */
  lastActivityAt: string;
  /** [SPEC] 최근 활동 표시 문자열 (예: "3시간 전", "2024.12.12") */
  lastActivityLabel: string;
  /** [BE] 최근 발행판을 승인한 사람. 승인자가 사용자로 이어지지 않으면 null이다 */
  lastEditedBy: DocumentOwner | null;
  /** [BE] 그 승인 시각(ISO). 발행판이 없으면 사람과 함께 null이다 */
  lastEditedAt: string | null;
}

/**
 * 검토 큐 한 줄. 작성자·신뢰도 필드는 두지 않는다 —
 * LLM 제안이라 작성자 개념이 없고 큐 응답에도 실리지 않는다.
 */
export interface ReviewQueueItemData {
  id: string;
  type: ReviewItemType;
  /** [BE] 행 제목 */
  title: string;
  /** [BE] 담당자 목록. 빈 배열이 미지정이고 행은 없음·1인·스택 세 갈래로 그린다 */
  owners: readonly DocumentOwner[];
  /** 대기 기간 표시 문자열 (예: "15시간 전") */
  waitingLabel: string;
  status: ChangeProposalStatus;
  /** [BE] rejected면 필수 (DB CHECK) */
  rejectionReason: string | null;
  /** [BE] stale 판정 기준 revision */
  baseRevisionId: string;
  /** 충돌(에러 아이콘) 행 — 상단 고정 여부는 미정 */
  hasConflictIcon: boolean;
  /**
   * [BE] 결정 권한(담당자 있으면 담당자만, 없으면 구성원 누구나) —
   * 서버가 계산해 내려주고 프론트는 소비만 한다.
   */
  canReview: boolean;
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
