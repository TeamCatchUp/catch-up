import type { SseRenderMode, SseStreamEventEnvelopeApi, StreamEvent } from '@/features/chat/types';
import { isRedisStreamIdAtOrBefore } from '@/features/chat/utils/stream/isRedisStreamId';

interface ApplyReconnectStreamWithCutoffParams {
  sessionId: string;
  cutoffId: string | null;
  reconnectChatStream: (sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => Promise<void>;
  handleStreamEvents: (events: readonly StreamEvent[], options?: { renderMode?: SseRenderMode }) => void;
  isCancelled?: () => boolean;
}

export const applyReconnectStreamWithCutoff = async ({
  sessionId,
  cutoffId,
  reconnectChatStream,
  handleStreamEvents,
  isCancelled = () => false,
}: ApplyReconnectStreamWithCutoffParams): Promise<void> => {
  const replayBuffer: StreamEvent[] = [];
  let hasLiveEvent = false;
  let replayFlushQueued = false;

  const flushReplayBuffer = () => {
    replayFlushQueued = false;
    if (isCancelled()) return;
    if (replayBuffer.length === 0) return;
    handleStreamEvents([...replayBuffer], { renderMode: 'instant' });
    replayBuffer.length = 0;
  };

  const queueReplayFlush = () => {
    if (replayFlushQueued || hasLiveEvent) return;
    replayFlushQueued = true;
    queueMicrotask(flushReplayBuffer);
  };

  await reconnectChatStream(sessionId, (envelope) => {
    if (isCancelled()) return;

    if (isRedisStreamIdAtOrBefore(envelope.id, cutoffId)) {
      replayBuffer.push(envelope.event);
      queueReplayFlush();
      return;
    }

    if (!hasLiveEvent) {
      flushReplayBuffer();
      hasLiveEvent = true;
    }

    handleStreamEvents([envelope.event], { renderMode: 'realtime' });
  });

  if (!hasLiveEvent) {
    flushReplayBuffer();
  }
};
