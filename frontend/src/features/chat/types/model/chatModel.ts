import type { EntityTypeApi, SourceTypeApi } from '@/features/chat/types/api/sourceApi';

/** 백엔드 SourceType과 동일 */
export type ChatSourceTypeModel = SourceTypeApi;

/** 답변 사이드바/배지용 출처 모델. 플랫폼은 source_type, 엔티티는 entity_type으로 분기. */
export interface ChatSourceModel {
  id: string;
  source_type: ChatSourceTypeModel;
  entity_type: EntityTypeApi;
  is_cited: boolean;
  repo: string;
  title: string;
  content: string;
  date: string;
  author: string;
  html_url: string;
  source_index: number;
  /** Jira 이슈키 (예: "CAT-297") */
  issue_key?: string;
  /** GitHub PR/Issue 번호 */
  github_number?: number;
}

export interface MessageModel {
  id: string;
  chat_history_id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSourceModel[];
  timestamp: string;
  has_feedback?: boolean;
  is_liked?: boolean;
  is_saved?: boolean;
}

export interface ChatDataModel {
  session_id: string;
  title: string;
  repo: string;
  messages: MessageModel[];
}
