import type { SseRenderMode, StreamEvent } from '@/features/chat/types';

type TokenEvent = Extract<StreamEvent, { type: 'token' }>;

const canMergeTokenEvents = (left: TokenEvent, right: TokenEvent): boolean =>
  !left.session_id || !right.session_id || left.session_id === right.session_id;

const mergeTokenEvents = (left: TokenEvent, right: TokenEvent): TokenEvent => ({
  ...left,
  session_id: left.session_id ?? right.session_id,
  token: `${left.token}${right.token}`,
});

export const normalizeStreamEventsForRenderMode = (
  events: readonly StreamEvent[],
  renderMode: SseRenderMode,
): StreamEvent[] => {
  if (renderMode === 'realtime') return [...events];

  const normalized: StreamEvent[] = [];
  let pendingToken: TokenEvent | null = null;

  const flushPendingToken = () => {
    if (!pendingToken) return;
    normalized.push(pendingToken);
    pendingToken = null;
  };

  for (const event of events) {
    if (event.type !== 'token') {
      flushPendingToken();
      normalized.push(event);
      continue;
    }

    if (pendingToken && canMergeTokenEvents(pendingToken, event)) {
      pendingToken = mergeTokenEvents(pendingToken, event);
      continue;
    }

    flushPendingToken();
    pendingToken = event;
  }

  flushPendingToken();
  return normalized;
};
