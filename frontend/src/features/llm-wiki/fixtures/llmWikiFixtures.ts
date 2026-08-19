import type { ReviewQueueFilterOption } from '../components/review-queue/ReviewQueueFilterSearchPanel';
import type {
  DocumentOwner,
  DocumentRowData,
  ReviewQueueItemData,
  ReviewStatCardData,
  TagItem,
} from '../types/llmWikiModel';

/** 담당자 표본 한 명. userId는 픽스처 안에서만 유일하면 되고 실제 계정과 무관하다 */
const documentOwner = (userId: number, displayName: string): DocumentOwner => ({
  userId,
  displayName,
  profileImageUrl: null,
});

const BASE_DOCUMENT_ROW: DocumentRowData = {
  id: 'doc-payment-retry',
  title: '결제 승인 실패 시 재시도 정책',
  breadcrumbs: [
    { kind: 'channel', label: '결제' },
    { kind: 'folder', label: '승인·실패 처리' },
  ],
  status: 'reviewed',
  owners: [documentOwner(1, '팀원F')],
  createdAt: '2024-09-02T01:00:00.000Z',
  lastActivityAt: '2024-12-15T06:00:00.000Z',
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
    owners: [documentOwner(2, '직원10')],
    createdAt: '2024-10-11T02:00:00.000Z',
    lastActivityAt: '2024-12-12T08:00:00.000Z',
    lastActivityLabel: '2024.12.12',
  }),
  // 담당자 2인 행 — 행은 첫 명만 렌더하지만 복수 계약이 픽스처에 실재해야 한다
  createDocumentRow({
    id: 'doc-refund-window',
    title: '환불 가능 기간 안내',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '환불' },
    ],
    owners: [documentOwner(3, '이진수'), documentOwner(12, '남궁현')],
    createdAt: '2024-08-20T03:00:00.000Z',
    lastActivityAt: '2024-12-14T09:00:00.000Z',
    lastActivityLabel: '어제',
  }),
  // 이하 9행은 표·페이지네이션을 실제 분량으로 보기 위한 것이다.
  // 담당자 이름은 전부 다르게 둔다 — 스토리가 담당자 셀을 이름으로 집어 좌표를 잰다.
  createDocumentRow({
    id: 'doc-login-mfa',
    title: '2단계 인증 실패 시 안내 문구',
    breadcrumbs: [
      { kind: 'channel', label: '계정' },
      { kind: 'folder', label: '인증' },
    ],
    status: 'pending_review',
    owners: [documentOwner(4, '김하은')],
    createdAt: '2024-11-01T04:00:00.000Z',
    lastActivityAt: '2024-12-12T05:00:00.000Z',
    lastActivityLabel: '2024.12.12',
  }),
  // 담당자 3인 행 — 위와 같은 이유
  createDocumentRow({
    id: 'doc-invoice-issue',
    title: '세금계산서 발행 기준',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '정산' },
    ],
    owners: [documentOwner(5, '최민우'), documentOwner(13, '서지호'), documentOwner(14, '임채원')],
    createdAt: '2024-07-15T05:00:00.000Z',
    lastActivityAt: '2024-12-13T07:00:00.000Z',
    lastActivityLabel: '3일 전',
  }),
  createDocumentRow({
    id: 'doc-plan-change',
    title: '요금제 변경 시 잔여 기간 처리',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '구독' },
    ],
    status: 'pending_review',
    owners: [documentOwner(6, '팀원G')],
    createdAt: '2024-11-20T06:00:00.000Z',
    lastActivityAt: '2024-12-11T04:00:00.000Z',
    lastActivityLabel: '2024.12.11',
  }),
  createDocumentRow({
    id: 'doc-data-export',
    title: '데이터 내보내기 요청 처리 절차',
    breadcrumbs: [
      { kind: 'channel', label: '계정' },
      { kind: 'folder', label: '데이터' },
    ],
    owners: [documentOwner(7, '직원30')],
    createdAt: '2024-06-30T07:00:00.000Z',
    lastActivityAt: '2024-12-10T03:00:00.000Z',
    lastActivityLabel: '2024.12.10',
  }),
  createDocumentRow({
    id: 'doc-notification-policy',
    title: '알림 발송 시간대 정책',
    breadcrumbs: [
      { kind: 'channel', label: '알림' },
      { kind: 'folder', label: '발송 정책' },
    ],
    status: 'pending_review',
    owners: [documentOwner(8, '오세훈')],
    createdAt: '2024-10-05T08:00:00.000Z',
    lastActivityAt: '2024-12-09T02:00:00.000Z',
    lastActivityLabel: '2024.12.09',
  }),
  createDocumentRow({
    id: 'doc-onboarding-guide',
    title: '신규 고객사 온보딩 체크리스트',
    breadcrumbs: [
      { kind: 'channel', label: '온보딩' },
      { kind: 'folder', label: '도입' },
    ],
    owners: [documentOwner(9, '문가영')],
    createdAt: '2024-05-18T09:00:00.000Z',
    lastActivityAt: '2024-12-08T01:00:00.000Z',
    lastActivityLabel: '2024.12.08',
  }),
  createDocumentRow({
    id: 'doc-sla-response',
    title: '장애 등급별 응답 시간 기준',
    breadcrumbs: [
      { kind: 'channel', label: '운영' },
      { kind: 'folder', label: 'SLA' },
    ],
    status: 'pending_review',
    owners: [documentOwner(10, '배수지')],
    createdAt: '2024-09-27T10:00:00.000Z',
    lastActivityAt: '2024-12-05T10:00:00.000Z',
    lastActivityLabel: '2024.12.05',
  }),
  createDocumentRow({
    id: 'doc-card-expiry',
    title: '카드 만료 임박 안내 발송 규칙',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '수단 관리' },
    ],
    owners: [documentOwner(11, '강태호')],
    createdAt: '2024-04-09T11:00:00.000Z',
    lastActivityAt: '2024-12-03T11:00:00.000Z',
    lastActivityLabel: '2024.12.03',
  }),
  createDocumentRow({
    id: 'doc-account-delete',
    title: '계정 삭제 요청과 보관 기간',
    breadcrumbs: [
      { kind: 'channel', label: '계정' },
      { kind: 'folder', label: '탈퇴' },
    ],
    status: 'pending_review',
    owners: [documentOwner(15, '윤서아')],
    createdAt: '2024-12-01T12:00:00.000Z',
    lastActivityAt: '2024-12-01T12:00:00.000Z',
    lastActivityLabel: '2024.12.01',
  }),
  // 담당자 미지정(빈 배열) 표본 — 지표 카드의 같은 이름 필터가 실제로 걸리는지 보려면 이 행이 있어야 한다
  createDocumentRow({
    id: 'doc-webhook-retry',
    title: '웹훅 재전송 정책',
    breadcrumbs: [
      { kind: 'channel', label: '운영' },
      { kind: 'folder', label: '연동' },
    ],
    owners: [],
    createdAt: '2024-03-14T13:00:00.000Z',
    lastActivityAt: '2024-11-28T13:00:00.000Z',
    lastActivityLabel: '2024.11.28',
  }),
];

const BASE_REVIEW_QUEUE_ITEM: ReviewQueueItemData = {
  id: 'proposal-payment-retry-v3',
  type: 'publish',
  title: '결제 승인 실패 시 재시도 정책 변경안',
  waitingLabel: '15시간 전',
  status: 'pending',
  rejectionReason: null,
  baseRevisionId: 'rev-0002',
  hasConflictIcon: false,
  canReview: true,
};

export const createReviewQueueItem = (overrides?: Partial<ReviewQueueItemData>): ReviewQueueItemData => ({
  ...BASE_REVIEW_QUEUE_ITEM,
  ...overrides,
});

// 모순(contradiction) 행 표본은 두지 않는다 — MVP 제외 결정, 유형·필드 계약은 보존
export const REVIEW_QUEUE_ITEM_FIXTURES: readonly ReviewQueueItemData[] = [
  createReviewQueueItem(),
  // 권한 없는 행 표본 — 권한은 제안마다 갈리므로(담당자 우선, 없으면 채널 관리자) 목록에 섞여 온다
  createReviewQueueItem({
    id: 'proposal-merge-refund',
    type: 'merge',
    title: '환불 문서 병합 제안',
    waitingLabel: '2일 전',
    canReview: false,
  }),
  createReviewQueueItem({
    id: 'proposal-rejected-example',
    status: 'rejected',
    rejectionReason: '근거 발췌가 현행 정책과 불일치',
    waitingLabel: '4일 전',
  }),
];

// 시안의 지표 4종. 8/14 갱신에서 중복 "검토 대기"가 사라지고 "전체 위키"가 들어왔다
export const REVIEW_STAT_CARD_FIXTURES: readonly ReviewStatCardData[] = [
  { id: 'stat-pending-review', label: '검토 대기', count: 7 },
  { id: 'stat-my-assigned', label: '내 담당', count: 150 },
  { id: 'stat-unassigned', label: '담당자 미지정', count: 150 },
  { id: 'stat-all-wiki', label: '전체 위키', count: 200 },
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
