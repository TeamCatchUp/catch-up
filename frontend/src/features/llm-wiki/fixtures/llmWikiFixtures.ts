import type { ReviewQueueFilterOption } from '../components/review-queue/ReviewQueueFilterSearchPanel';
import type { DocumentRowData, ReviewQueueItemData, ReviewStatCardData, TagItem } from '../types/llmWikiModel';

const BASE_DOCUMENT_ROW: DocumentRowData = {
  id: 'doc-payment-retry',
  title: '결제 승인 실패 시 재시도 정책',
  breadcrumbs: [
    { kind: 'channel', label: '결제' },
    { kind: 'folder', label: '승인·실패 처리' },
  ],
  status: 'reviewed',
  ownerName: '팀원F',
  ownerProfileImageUrl: null,
  lastActivityLabel: '3시간 전',
};

export const createDocumentRow = (overrides?: Partial<DocumentRowData>): DocumentRowData => ({
  ...BASE_DOCUMENT_ROW,
  ...overrides,
});

export const DOCUMENT_ROW_FIXTURES: readonly DocumentRowData[] = [
  createDocumentRow(),
  // 검토 대기 행 — 배지 위반 없이 표에 노출되는 두 번째 상태 표본
  createDocumentRow({
    id: 'doc-sso-session',
    title: 'SSO 세션 만료 시간 정책',
    breadcrumbs: [
      { kind: 'channel', label: '계정' },
      { kind: 'folder', label: '인증' },
    ],
    status: 'pending_review',
    ownerName: '직원10',
    lastActivityLabel: '2024.12.12',
  }),
  createDocumentRow({
    id: 'doc-refund-window',
    title: '환불 가능 기간 안내',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '환불' },
    ],
    ownerName: '이진수',
    lastActivityLabel: '어제',
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

export const createReviewQueueItem = (overrides?: Partial<ReviewQueueItemData>): ReviewQueueItemData => ({
  ...BASE_REVIEW_QUEUE_ITEM,
  ...overrides,
});

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

// 시안의 지표 3종. 시트에는 "검토 대기" 카드가 2장(일러스트 상이) 있으나 지표로는 1종이다
export const REVIEW_STAT_CARD_FIXTURES: readonly ReviewStatCardData[] = [
  { id: 'stat-pending-review', label: '검토 대기', count: 7 },
  { id: 'stat-my-assigned', label: '내 담당', count: 150 },
  { id: 'stat-unassigned', label: '담당자 미지정', count: 7 },
];

/**
 * 검토 큐 필터 담당자 축 표본. trailingLabel은 시안의 직책("PM") 자리이고 공급원은 미정이다.
 * 동명이인이 있어야 "id로 선택한다"는 계약이 스토리에서 실제로 밟힌다.
 */
export const REVIEW_QUEUE_ASSIGNEE_OPTIONS: readonly ReviewQueueFilterOption[] = [
  { id: 'u-seoyeon', label: '직원10', trailingLabel: 'PM' },
  { id: 'u-jinsu', label: '이진수', trailingLabel: 'PM' },
  { id: 'u-jinsu-2', label: '이진수', trailingLabel: 'BE' },
  { id: 'u-sibin', label: '팀원F', trailingLabel: 'FE' },
  { id: 'u-rogan', label: '팀원G', trailingLabel: 'FE' },
  { id: 'u-haeun', label: '김하은', trailingLabel: 'Design' },
  { id: 'u-minu', label: '최민우', trailingLabel: 'BE' },
  // 직책이 비는 행 — trailingLabel이 optional임을 스토리가 밟는다
  { id: 'u-external', label: '외부 협력자' },
];

/** 검토 큐 필터 대상 채널 축 표본. 채널은 직책이 없어 trailingLabel을 두지 않는다. */
export const REVIEW_QUEUE_CHANNEL_OPTIONS: readonly ReviewQueueFilterOption[] = [
  { id: 'ch-billing', label: '결제' },
  { id: 'ch-refund', label: '환불' },
  { id: 'ch-account', label: '계정' },
  { id: 'ch-notification', label: '알림' },
  { id: 'ch-onboarding', label: '온보딩' },
];

/**
 * 태그 탐색 목록 데이터. 카테고리로 묶지 않는다 — 태그 계층 구조는 범위 밖이다.
 * 스크롤이 걸리지 않는 개수이고, 스크롤 경계는 스토리가 별도 픽스처로 잰다.
 */
export const TAG_FIXTURES: readonly TagItem[] = [
  { id: 'tag-retry', name: '재시도 정책', documentCount: 4 },
  { id: 'tag-refund', name: '환불', documentCount: 6 },
  { id: 'tag-payment-failure', name: '결제 실패', documentCount: 9 },
  { id: 'tag-sso', name: 'SSO', documentCount: 3 },
  { id: 'tag-notification', name: '알림 설정', documentCount: 5 },
  { id: 'tag-export', name: '데이터 내보내기', documentCount: 2 },
];
