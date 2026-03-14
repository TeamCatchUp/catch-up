import type { SourceResponseApi } from '@/features/chat/types/api/sourceApi';

/**
 * fetch 기반 SSE 스트림 이벤트 유니온 타입.
 */
export type StreamEventApi =
  | { type: 'status'; session_id?: string; node: string; message: string }
  | { type: 'sources'; session_id?: string; sources?: SourceResponseApi[] }
  | { type: 'token'; session_id?: string; token: string };
