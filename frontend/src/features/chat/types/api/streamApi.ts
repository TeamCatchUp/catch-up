import type { SourceResponseApi } from '@/features/chat/types/api/sourceApi';

/**
 * fetch 기반 SSE 스트림 이벤트 유니온 타입.
 *
 * 백엔드(`stream_processor.py`)가 LangGraph events를 process/sources/token으로 변환해 emit한다.
 * - `'process'`: 노드 단위 진행 상황. node × status × (reasoning/content) 조합으로 step history를 구성한다.
 * - `'sources'`: 답변 본문에 사용된 source 목록.
 * - `'token'`: 답변 마크다운 stream chunk.
 */
export type StreamEventApi =
  | { type: 'sources'; session_id?: string; sources?: SourceResponseApi[] }
  | { type: 'token'; session_id?: string; token: string }
  | {
      type: 'process';
      session_id?: string;
      status: 'in_progress' | 'completed' | 'error';
      node: string;
      reasoning?: string | null;
      // node × status에 따라 다른 shape — 사용처에서 narrow
      content?: unknown;
    };
