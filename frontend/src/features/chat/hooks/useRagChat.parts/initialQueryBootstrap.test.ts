import type { Dispatch, RefObject, SetStateAction } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import chatService from '@/features/chat/services/chatService';
import { ChatStreamHttpError } from '@/features/chat/services/realChatService';
import type { ChatData, SseStreamEventEnvelopeApi, StreamEvent } from '@/features/chat/types';

import { useInitialQueryBootstrap } from './initialQueryBootstrap';
import type { ActiveStreamQuestion, StreamRuntimeRefs } from './types';

vi.mock('@/features/chat/services/chatService', () => ({
  default: {
    getGenerationStatus: vi.fn(),
  },
}));

const ref = <T,>(current: T): RefObject<T> => ({ current });

const token = (value: string): StreamEvent => ({
  type: 'token',
  session_id: 'session-1',
  token: value,
});

const buildChatData = (): ChatData => ({
  session_id: 'session-1',
  title: '',
  repo: '',
  messages: [],
});

const buildStreamRefs = (): StreamRuntimeRefs => ({
  streamingMessageIdRef: ref<string | null>(null),
  hasStreamedTokenRef: ref(false),
  latestSourcesRef: ref([]),
  latestUiSourcesRef: ref([]),
  streamInFlightRef: ref(false),
  hasAttemptedInitialStreamRef: ref(false),
  resolvedSessionIdRef: ref<string | undefined>('session-1'),
  activeQuestionRef: ref<ActiveStreamQuestion | null>(null),
});

describe('useInitialQueryBootstrap', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reconnects with cutoff-aware render modes when initial stream receives 409', async () => {
    const getGenerationStatus = vi.mocked(chatService.getGenerationStatus);
    getGenerationStatus.mockResolvedValue({ is_generating: true, cutoff_id: '10-0' });

    const streamChat = vi.fn().mockRejectedValue(new ChatStreamHttpError('conflict', 409));
    const reconnectChatStream = vi.fn(async (_sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => {
      onEnvelope({ id: '10-0', event: token('A') });
      onEnvelope({ id: '11-0', event: token('B') });
    });
    const handleStreamEvents = vi.fn();
    const finalizeAfterStreamClose = vi.fn().mockResolvedValue(undefined);

    renderHook(() =>
      useInitialQueryBootstrap({
        effectiveInitialQuery: 'hello',
        chatData: buildChatData(),
        isLoading: false,
        resolvedSessionId: 'session-1',
        streamChat,
        reconnectChatStream,
        handleStreamEvent: vi.fn(),
        handleStreamEvents,
        finalizeAfterStreamClose,
        handleAbortError: vi.fn(),
        beginAnswerLoading: vi.fn(),
        clearInitialQueryParam: vi.fn(),
        ensureInitialUserMessage: vi.fn(),
        setIsError: vi.fn() as Dispatch<SetStateAction<boolean>>,
        setIsLoading: vi.fn() as Dispatch<SetStateAction<boolean>>,
        setIsGenerating: vi.fn() as Dispatch<SetStateAction<boolean>>,
        streamRefs: buildStreamRefs(),
      }),
    );

    await waitFor(() => expect(finalizeAfterStreamClose).toHaveBeenCalled());

    expect(streamChat).toHaveBeenCalledWith('hello', 'session-1', expect.any(Function));
    expect(getGenerationStatus).toHaveBeenCalledWith('session-1');
    expect(reconnectChatStream).toHaveBeenCalledWith('session-1', expect.any(Function));
    expect(handleStreamEvents).toHaveBeenNthCalledWith(1, [token('A')], { renderMode: 'instant' });
    expect(handleStreamEvents).toHaveBeenNthCalledWith(2, [token('B')], { renderMode: 'realtime' });
  });
});
