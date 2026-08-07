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

// breadcrumb 종류. Figma가 아이콘을 정의한 것은 채널·폴더 2종뿐이라 나머지는 열어둔다
export type KnownBreadcrumbKind = 'channel' | 'folder';
export type BreadcrumbKind = KnownBreadcrumbKind | (string & {});

/** [SPEC] 채널 > 폴더 경로의 한 마디. 종류마다 Figma 아이콘이 갈려서 문자열로 뭉갤 수 없다 */
export interface DocumentBreadcrumb {
  kind: BreadcrumbKind;
  label: string;
}

/**
 * 대시보드 문서 표(17606:149822)의 행 계약.
 *
 * 문서_폴더 메인(17762:104801)·문서_채널 메인(17762:103743)의 행은 3열이
 * "연결 VOC & 고객사 수"이고 breadcrumbs가 없어 이 계약과 다르다 — 스펙 미결로 분리됐다.
 * 그래서 vocCount·customerCount는 여기 두지 않는다(어느 화면에도 breadcrumbs와 공존하지 않는다).
 */
export interface DocumentRowData {
  id: string;
  /** [BE] knowledge_artifacts.title */
  title: string;
  /** [SPEC] 채널 > 폴더 경로. 백엔드에 채널·폴더 개념 없음 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  status: DocumentStatus;
  /** 에러 아이콘 행 — 배지와의 공존 규칙 UNKNOWN(감사) 상태로 시각만 존재 */
  hasConflictIcon: boolean;
  /** [SPEC] 태그 목록. 행에는 첫 1개만 칩으로 보이고 나머지는 "+N"으로 접힌다 */
  tags: readonly string[];
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

/**
 * [SPEC] 태그는 전부 명세 유래 — 백엔드 스키마에 없음.
 *
 * 계층(카테고리 → 하위 태그)을 만들지 않는다. MVP 명세 §11이 "태그 계층 구조"를 범위 밖으로
 * 명시했고(2026-08-05-llm-wiki-mvp-design.md), 8/7 Figma 재확인에서도 대시보드 태그 영역
 * (17762:103078)은 그룹 헤더 없는 평평한 목록이었다. 그래서 이 타입이 태그 목록의 유일한 단위다.
 *
 * documentCount는 명세 §6("누적 문의 건수")에서 온 계약 보존용 필드다 — 태그 목록 시안에는
 * 건수 표기가 없으므로 TagCategoryList는 이 값을 렌더하지 않는다.
 */
export interface TagItem {
  id: string;
  name: string;
  documentCount: number;
}
