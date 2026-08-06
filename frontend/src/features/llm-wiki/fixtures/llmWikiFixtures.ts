import type {
  DocumentRowData,
  ReviewQueueItemData,
  ReviewStatCardData,
  TagCategory,
} from '../types/llmWikiModel';

const BASE_DOCUMENT_ROW: DocumentRowData = {
  id: 'doc-payment-retry',
  title: '결제 승인 실패 시 재시도 정책',
  breadcrumbs: ['결제', '승인·실패 처리'],
  status: 'reviewed',
  hasConflictIcon: false,
  vocCount: 12,
  customerCount: 4,
  lastActivityLabel: '3시간 전',
};

export const createDocumentRow = (overrides?: Partial<DocumentRowData>): DocumentRowData => ({
  ...BASE_DOCUMENT_ROW,
  ...overrides,
});

export const DOCUMENT_ROW_FIXTURES: readonly DocumentRowData[] = [
  createDocumentRow(),
  createDocumentRow({
    id: 'doc-refund-window',
    title: '환불 가능 기간 안내',
    breadcrumbs: ['결제', '환불'],
    vocCount: 7,
    customerCount: 2,
    lastActivityLabel: '어제',
  }),
  createDocumentRow({
    id: 'doc-sso-conflict',
    title: 'SSO 로그인 제한 정책',
    breadcrumbs: ['계정', '인증'],
    hasConflictIcon: true,
    vocCount: 21,
    customerCount: 9,
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

export const TAG_CATEGORY_FIXTURES: readonly TagCategory[] = [
  {
    id: 'category-billing',
    name: '결제',
    tags: [
      { id: 'tag-retry', name: '재시도 정책', documentCount: 4 },
      { id: 'tag-refund', name: '환불', documentCount: 6 },
    ],
  },
  {
    id: 'category-account',
    name: '계정',
    tags: [{ id: 'tag-sso', name: 'SSO', documentCount: 3 }],
  },
];
