import type { SourceResponseApi } from '@/features/chat/types/api/sourceApi';

export type StreamEventApi =
  | { type: 'sources'; session_id?: string; sources?: SourceResponseApi[] }
  | { type: 'token'; session_id?: string; token: string }
  | {
      type: 'process';
      session_id?: string;
      status: 'in_progress' | 'completed' | 'error';
      node: string;
      reasoning?: string | null;
      content?: unknown;
    };
