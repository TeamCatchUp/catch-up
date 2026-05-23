// 원문(Original Content) 조회 API 타입 — backend snake_case 매칭.
// 백엔드: POST /api/v1/search/original (ChannelTalk user_chat)
// schema: catchup/search/original/schemas/channel_talk.py + server/search/schemas.py
//
// block/button/form/file payload는 백엔드가 model_dump(exclude_none=True)로 직렬화 —
// null 필드는 키 자체가 생략되므로 payload 내부 필드는 전부 옵셔널(`?:`).
// 응답 최상위 url/next_cursor, item.author/created_at/updated_at 은 진짜 null 가능.

import type { SourceTypeApi } from '@/shared/types/sourceApi';

// --- content_type 별 payload ---

export interface OriginalTextPayload {
  text: string;
}

export interface OriginalBlock {
  // ChannelTalk block type — 알려진 값: 'text' | 'code' | 'bullets'
  block_type?: string;
  text?: string;
  label?: string;
  name?: string;
  value?: string;
  // ChannelTalk inline markup이 마크다운으로 변환된 결과. 변환 불필요 시 생략됨
  markdown?: string;
  raw_payload?: Record<string, unknown>;
}

export interface OriginalBlockPayload {
  blocks: OriginalBlock[];
}

export interface OriginalButton {
  text?: string;
  action?: string;
  value?: string;
  url?: string;
}

export interface OriginalButtonPayload {
  buttons: OriginalButton[];
}

export interface OriginalFormInput {
  label?: string;
  input_type?: string;
  data_type?: string;
  binding_key?: string;
  value?: string;
}

export interface OriginalForm {
  form_type?: string;
  submitted_at?: string;
  inputs: OriginalFormInput[];
  raw_payload?: Record<string, unknown>;
}

export interface OriginalFormPayload {
  form: OriginalForm;
}

export interface OriginalFile {
  file_key?: string;
  name?: string;
  content_type?: string;
  size?: number;
  url?: string;
}

export interface OriginalFilePayload {
  files: OriginalFile[];
}

// item.contents[] 한 요소 — content_type discriminated union
export type OriginalContent =
  | { content_type: 'text'; payload: OriginalTextPayload }
  | { content_type: 'block'; payload: OriginalBlockPayload }
  | { content_type: 'button'; payload: OriginalButtonPayload }
  | { content_type: 'form'; payload: OriginalFormPayload }
  | { content_type: 'file'; payload: OriginalFilePayload };

export type OriginalContentType = OriginalContent['content_type'];

// --- 메시지 item ---

export type OriginalAuthorType = 'customer' | 'manager';
export type OriginalVisibility = 'internal' | 'public';

export interface OriginalAuthor {
  id: string | null;
  name: string | null;
  type: OriginalAuthorType | null;
  email: string | null;
  avatar_url: string | null;
}

export interface OriginalMessageItem {
  id: string;
  type: 'message';
  visibility: OriginalVisibility;
  author: OriginalAuthor | null;
  contents: OriginalContent[];
  created_at: string | null;
  updated_at: string | null;
}

// --- 상담 전체 metadata ---
// detail 부재 시 channel_id/channel_name/user_chat_id 3개만 채워진다.

export interface OriginalCustomer {
  external_user_id: string;
  name?: string;
  email?: string;
  mobile_number?: string;
  landline_number?: string;
  avatar_url?: string;
  user_type?: string;
  member_id?: string;
  language?: string;
  country?: string;
  city?: string;
}

// managers[]가 관측된 응답에서 비어 있어 요소 형태는 미확정 — 최선의 추정.
export interface OriginalAssignmentManager {
  manager_id?: string;
  name?: string;
  email?: string;
  avatar_url?: string | null;
  role_id?: string;
}

// 응답엔 assignee_id만 오고 담당자 이름 필드는 없다 — managers[]에서 id로 조회.
export interface OriginalAssignment {
  assignee_id?: string;
  manager_ids?: string[];
  managers?: OriginalAssignmentManager[];
  first_assignee_id_after_open?: string;
}

export interface OriginalTag {
  key?: string;
  name?: string;
}

export interface OriginalMetadata {
  channel_id: string;
  channel_name: string;
  user_chat_id: string;
  name?: string | null;
  // 상담 설명 — detail 부재 시 생략, 값이 없으면 null.
  description?: string | null;
  state?: string;
  priority?: string | number;
  managed?: boolean;
  goal_state?: string;
  customer?: OriginalCustomer;
  assignment?: OriginalAssignment;
  tags?: OriginalTag[];
  // 디자인 미사용 — 정확한 형태 미확정(plan F1)
  timing?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  anchors?: Record<string, unknown>;
}

// --- 요청 / 응답 ---

export interface OriginalContentRequest {
  connector: SourceTypeApi;
  document_id: string;
  next_cursor?: string | null;
}

export interface OriginalContentResponse {
  connector: SourceTypeApi;
  entity_type: string;
  document_id: string;
  title: string;
  url: string | null;
  items: OriginalMessageItem[];
  metadata: OriginalMetadata;
  next_cursor: string | null;
  fetched_at: string;
}
