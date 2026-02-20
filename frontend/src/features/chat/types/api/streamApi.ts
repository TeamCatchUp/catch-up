import type { SourceResponseApi } from '@/features/chat/types/api/sourceApi';

/**
 * fetch 기반 SSE 스트림 이벤트 유니온 타입.
 */
export type StreamEventApi =
  | { type: 'status'; session_id?: string; node: string; message: string }
  | { type: 'sources'; session_id?: string; sources?: SourceResponseApi[] }
  | {
      type: 'source_candidates';
      session_id?: string;
      message_id?: string;
      sources?: SourceResponseApi[];
    }
  | { type: 'token'; session_id?: string; token: string }
  | {
      type: 'result';
      session_id?: string;
      message_id?: string;
      answer?: string;
      sources?: SourceResponseApi[];
      chat_history_id?: string;
      has_feedback?: boolean;
      related_jira_issues?: SourceResponseApi[];
    }
  | { type: 'error'; session_id?: string; message: string; retryable?: boolean }
  | { type: 'ping' };
