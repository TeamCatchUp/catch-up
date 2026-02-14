import type { BackendSourceApi } from '@/features/chat/types/api/sourceApi';
import type { PRPayloadModel } from '@/features/chat/types/model/chatModel';

/**
 * 구(notification) 기반 스트림 데이터 타입.
 * @interface RagNotificationDataApi
 */
export interface RagNotificationDataApi {
  session_id: string;
  type: 'status' | 'interrupt' | 'result';
  node: string;
  message?: string;
  payload?: PRPayloadModel[];
  response?: {
    session_id: string;
    answer: string;
    sources: BackendSourceApi[];
    chat_history_id: string;
    has_feedback?: boolean;
  };
  related_jira_issues?: BackendSourceApi[];
}

/**
 * 구(notification) 기반 래퍼 타입.
 * @interface RagNotificationApi
 */
export interface RagNotificationApi {
  target: 'CHAT' | 'MESSAGE';
  type: 'CONNECT' | 'RAG_IN_PROGRESS' | 'RAG_INTERRUPT' | 'RAG_DONE';
  message: string | null;
  data: RagNotificationDataApi | null;
}

/**
 * fetch 기반 SSE 스트림 이벤트 유니온 타입.
 */
export type StreamEventApi =
  | { type: 'status'; session_id?: string; node: string; message: string }
  | { type: 'sources'; session_id?: string; sources?: BackendSourceApi[] }
  | {
      type: 'source_candidates';
      session_id?: string;
      message_id?: string;
      sources?: BackendSourceApi[];
    }
  | { type: 'token'; session_id?: string; token: string }
  | { type: 'delta'; session_id?: string; message_id?: string; delta: string; sequence?: number }
  | { type: 'interrupt'; payload: PRPayloadModel[] }
  | {
      type: 'result';
      session_id?: string;
      message_id?: string;
      answer?: string;
      sources?: BackendSourceApi[];
      chat_history_id?: string;
      has_feedback?: boolean;
      related_jira_issues?: BackendSourceApi[];
    }
  | { type: 'error'; session_id?: string; message: string; retryable?: boolean }
  | { type: 'ping' };
