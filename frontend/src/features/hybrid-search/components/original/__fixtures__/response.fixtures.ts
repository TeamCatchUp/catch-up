// dev preview 갤러리용 전체 ChannelTalk 원문 목 데이터.
// 날짜 그룹 여러 개 + 메시지·콘텐츠 타입이 섞인 현실적인 전체 대화 1건.

import type {
  ChannelTalkOriginalContentResponse,
  OriginalMessageItem,
} from '../../../types/originalApi';
import {
  blockContentCodeShort,
  blockContentMixed,
  buttonContentMultiple,
  fileContentMultiple,
  formContentVariedInputs,
  textContentLong,
  textContentShort,
} from './content.fixtures';
import { metadataFull } from './metadata.fixtures';

// 날짜 그룹 1 — 2026-05-20.
const day1Items: OriginalMessageItem[] = [
  {
    id: 'conv-001',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'cust-001',
      name: '직원04',
      type: 'customer',
      email: 'minsoo.kim@example.com',
      avatar_url: 'https://i.pravatar.cc/80?img=12',
    },
    contents: [
      { content_type: 'text', payload: { text: '안녕하세요, 결제가 자꾸 실패하는데 확인 부탁드립니다.' } },
    ],
    created_at: '2026-05-20T09:30:00+09:00',
    updated_at: null,
  },
  {
    id: 'conv-002',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'mgr-001',
      name: '이지은 상담원',
      type: 'manager',
      email: 'jieun.lee@catchup.example',
      avatar_url: 'https://i.pravatar.cc/80?img=45',
    },
    contents: [textContentLong, buttonContentMultiple],
    created_at: '2026-05-20T09:32:00+09:00',
    updated_at: null,
  },
  {
    id: 'conv-003',
    type: 'message',
    visibility: 'internal',
    author: {
      id: 'mgr-001',
      name: '이지은 상담원',
      type: 'manager',
      email: 'jieun.lee@catchup.example',
      avatar_url: 'https://i.pravatar.cc/80?img=45',
    },
    contents: [
      { content_type: 'text', payload: { text: '결제 대행사 점검 시간 결제팀에 재확인했습니다.' } },
    ],
    created_at: '2026-05-20T09:34:00+09:00',
    updated_at: null,
  },
  {
    id: 'conv-004',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'cust-001',
      name: '직원04',
      type: 'customer',
      email: 'minsoo.kim@example.com',
      avatar_url: 'https://i.pravatar.cc/80?img=12',
    },
    contents: [textContentShort],
    created_at: '2026-05-20T09:48:00+09:00',
    updated_at: null,
  },
];

// 날짜 그룹 2 — 2026-05-21.
const day2Items: OriginalMessageItem[] = [
  {
    id: 'conv-005',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'cust-001',
      name: '직원04',
      type: 'customer',
      email: 'minsoo.kim@example.com',
      avatar_url: 'https://i.pravatar.cc/80?img=12',
    },
    contents: [
      { content_type: 'text', payload: { text: '점검 후 다시 시도했더니 결제가 됐어요. 감사합니다!' } },
    ],
    created_at: '2026-05-21T10:05:00+09:00',
    updated_at: null,
  },
  {
    id: 'conv-006',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'mgr-001',
      name: '이지은 상담원',
      type: 'manager',
      email: 'jieun.lee@catchup.example',
      avatar_url: 'https://i.pravatar.cc/80?img=45',
    },
    contents: [blockContentMixed],
    created_at: '2026-05-21T10:07:00+09:00',
    updated_at: null,
  },
  {
    id: 'conv-007',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'mgr-001',
      name: '이지은 상담원',
      type: 'manager',
      email: 'jieun.lee@catchup.example',
      avatar_url: 'https://i.pravatar.cc/80?img=45',
    },
    contents: [blockContentCodeShort, fileContentMultiple],
    created_at: '2026-05-21T10:09:00+09:00',
    updated_at: null,
  },
];

// 날짜 그룹 3 — 2026-05-22.
const day3Items: OriginalMessageItem[] = [
  {
    id: 'conv-008',
    type: 'message',
    visibility: 'public',
    author: {
      id: 'mgr-001',
      name: '이지은 상담원',
      type: 'manager',
      email: 'jieun.lee@catchup.example',
      avatar_url: 'https://i.pravatar.cc/80?img=45',
    },
    contents: [
      { content_type: 'text', payload: { text: '상담 만족도 조사를 부탁드립니다.' } },
      formContentVariedInputs,
    ],
    created_at: '2026-05-22T11:20:00+09:00',
    updated_at: null,
  },
];

// 현실적인 전체 대화 — 3개 날짜 그룹, 메시지/콘텐츠 타입 혼합.
export const fullConversationResponse: ChannelTalkOriginalContentResponse = {
  connector: 'channel_talk',
  entity_type: 'user_chat',
  document_id: 'channel_talk:user_chat:55012',
  title: '결제 실패 문의 — 직원04',
  url: 'https://desk.channel.io/#/channels/channel-001/user_chats/user-chat-55012',
  items: [...day1Items, ...day2Items, ...day3Items],
  metadata: metadataFull,
  next_cursor: null,
  fetched_at: '2026-05-23T08:00:00+09:00',
};

// 메시지 0건 — empty 상태 케이스.
export const emptyConversationResponse: ChannelTalkOriginalContentResponse = {
  connector: 'channel_talk',
  entity_type: 'user_chat',
  document_id: 'channel_talk:user_chat:55099',
  title: '신규 상담 — 미응대',
  url: null,
  items: [],
  metadata: {
    channel_id: 'channel-001',
    channel_name: '캐치업 고객지원',
    user_chat_id: 'user-chat-55099',
  },
  next_cursor: null,
  fetched_at: '2026-05-23T08:00:00+09:00',
};
