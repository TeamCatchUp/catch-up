import { API } from '@/shared/api/endpoints';

import type { SyncStreamEvent } from '../types/sync';

export type SyncStreamCallback = (event: SyncStreamEvent) => void;

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

/**
 * SSE 블록 파싱 — "data:" 라인에서 JSON 추출
 * event: 라인은 무시 (event_type이 JSON payload에 포함되어 있음)
 */
function parseSseBlock(block: string): SyncStreamEvent | null {
  const dataLines = block
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (dataLines.length === 0) return null;

  try {
    return JSON.parse(dataLines.join('\n')) as SyncStreamEvent;
  } catch {
    return null;
  }
}

/** 단일 SSE 연결 수행 (재시도 없음) */
async function readStream(
  jobId: string,
  onEvent: SyncStreamCallback,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(API.sync.jobStream(jobId), {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'text/event-stream' },
    signal,
  });

  if (!res.ok) throw new Error(`SSE ${res.status}`);
  if (!res.body) throw new Error('SSE empty body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';

      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (event) onEvent(event);
      }

      if (done) break;
    }

    const tail = buffer.trim();
    if (tail) {
      const event = parseSseBlock(tail);
      if (event) onEvent(event);
    }
  } finally {
    reader.cancel();
  }
}

export interface SyncStreamOptions {
  onEvent: SyncStreamCallback;
  /** SSE 연결이 재시도 불가능한 에러로 종료될 때 호출 */
  onError?: (error: Error) => void;
}

/**
 * fetch + ReadableStream 기반 SSE 연결 (자동 재시도 포함)
 *
 * - 네트워크 에러 / 5xx 시 exponential backoff 재시도 (최대 3회)
 * - 4xx 에러는 재시도 없이 즉시 종료
 * - AbortSignal로 취소 가능
 */
export async function connectSyncStream(
  jobId: string,
  { onEvent, onError }: SyncStreamOptions,
  signal: AbortSignal,
): Promise<void> {
  let retries = 0;

  while (retries <= MAX_RETRIES) {
    try {
      await readStream(jobId, onEvent, signal);
      return; // 정상 종료 (서버가 스트림을 닫음)
    } catch (err) {
      if (signal.aborted) return; // 의도적 취소

      const isRetryable =
        err instanceof TypeError || // 네트워크 에러
        (err instanceof Error && err.message.startsWith('SSE 5'));

      if (!isRetryable || retries >= MAX_RETRIES) {
        onError?.(err instanceof Error ? err : new Error(String(err)));
        return;
      }

      retries++;
      const delay = BASE_DELAY_MS * 2 ** (retries - 1);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}
