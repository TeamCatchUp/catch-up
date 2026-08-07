import type {
  DocumentRowData,
  ReviewQueueItemData,
  ReviewStatCardData,
  TagItem,
} from '../types/llmWikiModel';

// 태그 3개 = 칩 1개 + "+2" — Figma 대시보드 행(17762:103678)이 보여주는 조합 그대로다
const BASE_DOCUMENT_ROW: DocumentRowData = {
  id: 'doc-payment-retry',
  title: '결제 승인 실패 시 재시도 정책',
  breadcrumbs: [
    { kind: 'channel', label: '결제' },
    { kind: 'folder', label: '승인·실패 처리' },
  ],
  status: 'reviewed',
  hasConflictIcon: false,
  tags: ['재시도 정책', '결제 실패', 'PG 연동'],
  lastActivityLabel: '3시간 전',
};

export const createDocumentRow = (overrides?: Partial<DocumentRowData>): DocumentRowData => ({
  ...BASE_DOCUMENT_ROW,
  ...overrides,
});

export const DOCUMENT_ROW_FIXTURES: readonly DocumentRowData[] = [
  createDocumentRow(),
  // 태그 1개 — "+N" 칩이 붙지 않는 행
  createDocumentRow({
    id: 'doc-refund-window',
    title: '환불 가능 기간 안내',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '환불' },
    ],
    tags: ['환불'],
    lastActivityLabel: '어제',
  }),
  createDocumentRow({
    id: 'doc-sso-conflict',
    title: 'SSO 로그인 제한 정책',
    breadcrumbs: [
      { kind: 'channel', label: '계정' },
      { kind: 'folder', label: '인증' },
    ],
    hasConflictIcon: true,
    tags: ['SSO', '보안'],
    lastActivityLabel: '15분 전',
  }),
];

const BASE_REVIEW_QUEUE_ITEM: ReviewQueueItemData = {
  id: 'proposal-payment-retry-v3',
  type: 'publish',
  title: '결제 승인 실패 시 재시도 정책 변경안',
  authorName: '직원10',
  authorProfileImageUrl: null,
  waitingLabel: '15시간 전',
  confidence: 0.62,
  status: 'pending',
  rejectionReason: null,
  baseRevisionId: 'rev-0002',
  hasConflictIcon: false,
};

export const createReviewQueueItem = (
  overrides?: Partial<ReviewQueueItemData>,
): ReviewQueueItemData => ({ ...BASE_REVIEW_QUEUE_ITEM, ...overrides });

export const REVIEW_QUEUE_ITEM_FIXTURES: readonly ReviewQueueItemData[] = [
  createReviewQueueItem({
    id: 'proposal-sso-contradiction',
    type: 'contradiction',
    title: 'SSO 세션 만료 시간 상충',
    confidence: 0.31,
    hasConflictIcon: true,
  }),
  createReviewQueueItem(),
  createReviewQueueItem({
    id: 'proposal-merge-refund',
    type: 'merge',
    title: '환불 문서 병합 제안',
    confidence: 0.84,
    waitingLabel: '2일 전',
  }),
  createReviewQueueItem({
    id: 'proposal-rejected-example',
    status: 'rejected',
    rejectionReason: '근거 발췌가 현행 정책과 불일치',
    waitingLabel: '4일 전',
  }),
];

export const REVIEW_STAT_CARD_FIXTURES: readonly ReviewStatCardData[] = [
  { id: 'stat-pending-review', label: '검토 대기', count: 12 },
  { id: 'stat-open-contradictions', label: '미해결 충돌', count: 3 },
  { id: 'stat-untagged', label: '태그 미분류', count: 8 },
  { id: 'stat-stale-documents', label: '장기 미변경 문서', count: 5 },
];

/**
 * 대시보드 태그 영역 좌측 목록(17762:103078)의 데이터.
 *
 * 카테고리로 묶지 않는다 — 명세 §11이 태그 계층 구조를 범위 밖으로 못박았고 시안도 평평한 목록이다.
 * 6개는 Figma 좌측 목록(8행, 300px 높이 = 스크롤)보다 적은 수라 스크롤이 걸리지 않는다.
 * 스크롤 경계는 TagNavigationList 스토리가 별도 픽스처로 잰다.
 */
export const TAG_FIXTURES: readonly TagItem[] = [
  { id: 'tag-retry', name: '재시도 정책', documentCount: 4 },
  { id: 'tag-refund', name: '환불', documentCount: 6 },
  { id: 'tag-payment-failure', name: '결제 실패', documentCount: 9 },
  { id: 'tag-sso', name: 'SSO', documentCount: 3 },
  { id: 'tag-notification', name: '알림 설정', documentCount: 5 },
  { id: 'tag-export', name: '데이터 내보내기', documentCount: 2 },
];
