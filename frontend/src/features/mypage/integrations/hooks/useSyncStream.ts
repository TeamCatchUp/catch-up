import { useCallback, useEffect, useRef } from 'react';

import { API } from '@/shared/api/endpoints';

import type { SyncStreamEvent } from '../types/sync';

type SyncStreamCallback = (event: SyncStreamEvent) => void;

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

/**
 * fetch + ReadableStream 기반 SSE 연결
 * AbortSignal로 취소 가능
 */
export async function connectSyncStream(
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

  if (!res.ok) throw new Error(`SSE stream error: ${res.status}`);
  if (!res.body) throw new Error('SSE stream error: empty response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

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
}

/**
 * Sync SSE 스트림 구독 훅.
 *
 * jobId가 주어지면 SSE 연결을 열고, 이벤트마다 onEvent 콜백 호출.
 * jobId가 null이면 연결하지 않음. jobId가 바뀌면 기존 연결을 끊고 재연결.
 */
export function useSyncStream(jobId: string | null, onEvent: SyncStreamCallback) {
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback((id: string, signal: AbortSignal) => {
    connectSyncStream(id, (event) => onEventRef.current(event), signal).catch(() => {
      // 연결 종료 (abort 또는 네트워크 에러) — 조용히 무시
    });
  }, []);

  useEffect(() => {
    if (!jobId) return;

    const controller = new AbortController();
    connect(jobId, controller.signal);

    return () => {
      controller.abort();
    };
  }, [jobId, connect]);
}
