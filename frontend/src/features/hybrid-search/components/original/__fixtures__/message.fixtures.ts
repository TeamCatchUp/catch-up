// dev preview 갤러리용 OriginalMessageItem 목 데이터 — 메시지 변형 케이스 매트릭스.
// customer/manager × public/internal, author null, avatar null, name 누락,
// created_at null, 한 메시지에 여러 content.

import type { OriginalAuthor, OriginalMessageItem } from '../../../types/originalApi';
import {
  blockContentMarkdown,
  buttonContentMultiple,
  fileContentSingle,
  textContentLong,
  textContentShort,
} from './content.fixtures';

// --- author 샘플 ---

const customerAuthor: OriginalAuthor = {
  id: 'cust-001',
  name: '직원04',
  type: 'customer',
  email: 'minsoo.kim@example.com',
  avatar_url: 'https://i.pravatar.cc/80?img=12',
};

const managerAuthor: OriginalAuthor = {
  id: 'mgr-001',
  name: '이지은 상담원',
  type: 'manager',
  email: 'jieun.lee@catchup.example',
  avatar_url: 'https://i.pravatar.cc/80?img=45',
};

// --- 메시지 변형 ---

// 고객의 공개 메시지 — 배경 없음.
export const messageCustomerPublic: OriginalMessageItem = {
  id: 'msg-customer-public',
  type: 'message',
  visibility: 'public',
  author: customerAuthor,
  contents: [textContentShort],
  created_at: '2026-05-20T09:30:00+09:00',
  updated_at: null,
};

// 상담원의 공개 메시지 — 배경 없음.
export const messageManagerPublic: OriginalMessageItem = {
  id: 'msg-manager-public',
  type: 'message',
  visibility: 'public',
  author: managerAuthor,
  contents: [textContentLong],
  created_at: '2026-05-20T09:32:00+09:00',
  updated_at: '2026-05-20T09:33:10+09:00',
};

// 내부 대화 — visibility=internal 일 때만 주황 배경.
export const messageInternal: OriginalMessageItem = {
  id: 'msg-internal',
  type: 'message',
  visibility: 'internal',
  author: managerAuthor,
  contents: [
    {
      content_type: 'text',
      payload: { text: '이 건은 결제팀에 에스컬레이션 필요합니다. @박팀장 확인 부탁드려요.' },
    },
  ],
  created_at: '2026-05-20T09:34:00+09:00',
  updated_at: null,
};

// author 자체가 null.
export const messageAuthorNull: OriginalMessageItem = {
  id: 'msg-author-null',
  type: 'message',
  visibility: 'public',
  author: null,
  contents: [{ content_type: 'text', payload: { text: '작성자 정보가 없는 메시지입니다.' } }],
  created_at: '2026-05-20T09:35:00+09:00',
  updated_at: null,
};

// avatar_url 만 null.
export const messageAvatarNull: OriginalMessageItem = {
  id: 'msg-avatar-null',
  type: 'message',
  visibility: 'public',
  author: { ...customerAuthor, id: 'cust-002', name: '직원10', avatar_url: null },
  contents: [{ content_type: 'text', payload: { text: '아바타 이미지가 없는 고객 메시지입니다.' } }],
  created_at: '2026-05-20T09:36:00+09:00',
  updated_at: null,
};

// name 누락 — 이름 placeholder 케이스.
export const messageNameNull: OriginalMessageItem = {
  id: 'msg-name-null',
  type: 'message',
  visibility: 'public',
  author: { ...managerAuthor, id: 'mgr-002', name: null },
  contents: [{ content_type: 'text', payload: { text: '이름 정보가 없는 상담원 메시지입니다.' } }],
  created_at: '2026-05-20T09:37:00+09:00',
  updated_at: null,
};

// created_at 이 null — 시각 placeholder 케이스.
export const messageCreatedAtNull: OriginalMessageItem = {
  id: 'msg-created-at-null',
  type: 'message',
  visibility: 'public',
  author: customerAuthor,
  contents: [{ content_type: 'text', payload: { text: '작성 시각 정보가 없는 메시지입니다.' } }],
  created_at: null,
  updated_at: null,
};

// 한 메시지에 여러 content — block + button.
export const messageMultiContentBlockButton: OriginalMessageItem = {
  id: 'msg-multi-block-button',
  type: 'message',
  visibility: 'public',
  author: managerAuthor,
  contents: [blockContentMarkdown, buttonContentMultiple],
  created_at: '2026-05-20T09:40:00+09:00',
  updated_at: null,
};

// 한 메시지에 여러 content — block + file.
export const messageMultiContentBlockFile: OriginalMessageItem = {
  id: 'msg-multi-block-file',
  type: 'message',
  visibility: 'public',
  author: managerAuthor,
  contents: [
    {
      content_type: 'block',
      payload: {
        blocks: [{ block_type: 'text', text: '요청하신 결제 내역서를 첨부드립니다.' }],
      },
    },
    fileContentSingle,
  ],
  created_at: '2026-05-20T09:42:00+09:00',
  updated_at: null,
};

// 갤러리에서 한 번에 순회할 수 있는 변형 목록.
export const messageItemVariants: { label: string; item: OriginalMessageItem }[] = [
  { label: '고객 · 공개', item: messageCustomerPublic },
  { label: '상담원 · 공개', item: messageManagerPublic },
  { label: '내부 대화 (배경)', item: messageInternal },
  { label: 'author null', item: messageAuthorNull },
  { label: 'avatar_url null', item: messageAvatarNull },
  { label: 'name 누락', item: messageNameNull },
  { label: 'created_at null', item: messageCreatedAtNull },
  { label: '다중 content (block+button)', item: messageMultiContentBlockButton },
  { label: '다중 content (block+file)', item: messageMultiContentBlockFile },
];
