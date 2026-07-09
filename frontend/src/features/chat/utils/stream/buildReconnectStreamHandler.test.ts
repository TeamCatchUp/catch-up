import { describe, expect, it, vi } from 'vitest';

import type { SseStreamEventEnvelopeApi, StreamEvent } from '@/features/chat/types';

import { applyReconnectStreamWithCutoff } from './buildReconnectStreamHandler';

const token = (value: string): StreamEvent => ({
  type: 'token',
  session_id: 'session-1',
  token: value,
});

describe('applyReconnectStreamWithCutoff', () => {
  it('cutoff 이전 replay는 instant로 묶고 이후 live는 realtime으로 처리한다', async () => {
    const calls: Array<{ events: readonly StreamEvent[]; renderMode: string | undefined }> = [];
    const envelopes: SseStreamEventEnvelopeApi[] = [
      { id: '10-0', event: token('안') },
      { id: '10-1', event: token('녕') },
      { id: '11-0', event: token('!') },
    ];

    await applyReconnectStreamWithCutoff({
      sessionId: 'session-1',
      cutoffId: '10-1',
      reconnectChatStream: async (_sessionId, onEnvelope) => {
        envelopes.forEach(onEnvelope);
      },
      handleStreamEvents: (events, options) => {
        calls.push({ events, renderMode: options?.renderMode });
      },
    });

    expect(calls).toEqual([
      { events: [token('안'), token('녕')], renderMode: 'instant' },
      { events: [token('!')], renderMode: 'realtime' },
    ]);
  });

  it('cutoff가 없거나 envelope id가 없으면 live 이벤트로 처리한다', async () => {
    const handleStreamEvents = vi.fn();

    await applyReconnectStreamWithCutoff({
      sessionId: 'session-1',
      cutoffId: null,
      reconnectChatStream: async (_sessionId, onEnvelope) => {
        onEnvelope({ event: token('A') });
      },
      handleStreamEvents,
    });

    expect(handleStreamEvents).toHaveBeenCalledWith([token('A')], { renderMode: 'realtime' });
  });

  it('cancelled 상태에서는 buffered replay를 렌더링하지 않는다', async () => {
    const handleStreamEvents = vi.fn();

    await applyReconnectStreamWithCutoff({
      sessionId: 'session-1',
      cutoffId: '10-0',
      reconnectChatStream: async (_sessionId, onEnvelope) => {
        onEnvelope({ id: '10-0', event: token('A') });
      },
      handleStreamEvents,
      isCancelled: () => true,
    });

    expect(handleStreamEvents).not.toHaveBeenCalled();
  });
});
