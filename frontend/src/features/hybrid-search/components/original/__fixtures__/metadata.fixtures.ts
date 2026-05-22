// dev preview 갤러리용 OriginalMetadata 목 데이터.
// full / 태그 없음 / detail 부재(channel_id/channel_name/user_chat_id 3개만).

import type { OriginalCustomer, OriginalMetadata } from '../../../types/originalApi';

// --- customer 샘플 ---

export const customerFull: OriginalCustomer = {
  external_user_id: 'ext-user-7781',
  name: '직원04',
  email: 'minsoo.kim@example.com',
  mobile_number: '010-1234-5678',
  landline_number: '02-789-0123',
  avatar_url: 'https://i.pravatar.cc/80?img=12',
  user_type: 'member',
  member_id: 'member-7781',
  language: 'ko',
  country: 'KR',
  city: 'Seoul',
};

// 일부 필드만 채워진 customer — "없음" placeholder 케이스.
export const customerPartial: OriginalCustomer = {
  external_user_id: 'ext-user-3310',
  name: '익명 고객',
  language: 'ko',
};

// --- metadata 변형 ---

// 전체 — detail 의 대부분 필드가 채워진 케이스.
export const metadataFull: OriginalMetadata = {
  channel_id: 'channel-001',
  channel_name: '캐치업 고객지원',
  user_chat_id: 'user-chat-55012',
  description: '결제 오류로 환불을 요청하는 문의입니다.',
  state: 'closed',
  priority: 'high',
  managed: true,
  goal_state: 'resolved',
  customer: customerFull,
  assignment: {
    assignee_id: 'mgr-001',
    manager_ids: ['mgr-001', 'mgr-002'],
    managers: [
      { manager_id: 'mgr-001', name: '이지은', email: 'jieun.lee@catchup.example', role_id: 'agent' },
      { manager_id: 'mgr-002', name: '박팀장', email: 'team.park@catchup.example', role_id: 'lead' },
    ],
    first_assignee_id_after_open: 'mgr-001',
  },
  tags: [
    { key: 'billing', name: '결제' },
    { key: 'refund', name: '환불' },
    { key: 'urgent', name: '긴급' },
  ],
  timing: { opened_at: '2026-05-20T09:30:00+09:00', closed_at: '2026-05-20T09:55:00+09:00' },
  metrics: { message_count: 12, resolution_minutes: 25 },
  anchors: { first_message_id: 'msg-customer-public' },
};

// 태그 없음 — tags 부재.
export const metadataNoTags: OriginalMetadata = {
  channel_id: 'channel-001',
  channel_name: '캐치업 고객지원',
  user_chat_id: 'user-chat-55013',
  state: 'open',
  priority: 'medium',
  managed: true,
  goal_state: 'inProgress',
  customer: customerPartial,
  assignment: {
    assignee_id: 'mgr-003',
    manager_ids: ['mgr-003'],
    managers: [
      { manager_id: 'mgr-003', name: '최상담', email: 'sangdam.choi@catchup.example', role_id: 'agent' },
    ],
  },
  timing: { opened_at: '2026-05-21T14:10:00+09:00' },
};

// detail 부재 — channel_id/channel_name/user_chat_id 3개만.
export const metadataDetailAbsent: OriginalMetadata = {
  channel_id: 'channel-002',
  channel_name: '캐치업 세일즈',
  user_chat_id: 'user-chat-55014',
};

// 갤러리에서 한 번에 순회할 수 있는 변형 목록.
export const metadataVariants: { label: string; metadata: OriginalMetadata }[] = [
  { label: '전체', metadata: metadataFull },
  { label: '태그 없음', metadata: metadataNoTags },
  { label: 'detail 부재 (3키만)', metadata: metadataDetailAbsent },
];
