import type { SourceResponseApi } from '@/features/chat/types/api/sourceApi';

/** RAG 파이프라인 노드 1건의 진행 이벤트. SSE process 본문과 히스토리 pipeline_result의 공통 shape. */
export interface PipelineEventApi {
  node: string;
  status: 'in_progress' | 'completed' | 'error';
  reasoning?: string | null;
  content?: unknown;
}

export type StreamEventApi =
  | { type: 'sources'; session_id?: string; sources?: SourceResponseApi[] }
  | { type: 'token'; session_id?: string; token: string }
  | ({ type: 'process'; session_id?: string } & PipelineEventApi);

export interface ChatGenerationStatusResponseApi {
  is_generating: boolean;
  cutoff_id: string | null;
}

export interface ChatCancelGenerationResponseApi {
  status: 'cancelled' | 'not_running';
}

export interface SseStreamEventEnvelopeApi {
  id?: string;
  event: StreamEventApi;
}

export type SseRenderMode = 'instant' | 'realtime';
