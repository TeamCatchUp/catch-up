import type { Dispatch, RefObject, SetStateAction } from 'react';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import chatService from '@/features/chat/services/chatService';
import { ChatStreamHttpError } from '@/features/chat/services/realChatService';
import type { ChatData, PipelineQueryType, SseStreamEventEnvelopeApi, StepRow, StreamEvent } from '@/features/chat/types';

import { useMessageActions } from './messageActions';
import type { ActiveStreamQuestion, StreamRuntimeRefs } from './types';

vi.mock('@/features/chat/services/chatService', () => ({
  default: {
    getGenerationStatus: vi.fn(),
    resetLastTurn: vi.fn(),
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
  title: 'title',
  repo: '',
  messages: [
    {
      id: 'user-1',
      role: 'user',
      content: 'first',
      timestamp: '2026-07-09T09:00:00.000Z',
    },
  ],
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

describe('useMessageActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses cutoff-aware reconnect render modes when send receives 409', async () => {
    const getGenerationStatus = vi.mocked(chatService.getGenerationStatus);
    getGenerationStatus.mockResolvedValue({ is_generating: true, cutoff_id: '10-0' });

    const streamChat = vi.fn().mockRejectedValue(new ChatStreamHttpError('conflict', 409));
    const reconnectChatStream = vi.fn(async (_sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => {
      onEnvelope({ id: '10-0', event: token('A') });
      onEnvelope({ id: '11-0', event: token('B') });
    });
    const handleStreamEvents = vi.fn();
    const finalizeAfterStreamClose = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useMessageActions({
        chatData: buildChatData(),
        isLoading: false,
        resolvedSessionId: 'session-1',
        streamChat,
        handleStreamEvent: vi.fn(),
        handleStreamEvents,
        finalizeAfterStreamClose,
        handleAbortError: vi.fn(),
        beginAnswerLoading: vi.fn(),
        appendAssistantAnswer: vi.fn(),
        cancelGeneration: vi.fn(),
        reconnectChatStream,
        abortStream: vi.fn(),
        markStopped: vi.fn(),
        setChatData: vi.fn() as Dispatch<SetStateAction<ChatData | null>>,
        setIsLoading: vi.fn() as Dispatch<SetStateAction<boolean>>,
        setIsError: vi.fn() as Dispatch<SetStateAction<boolean>>,
        setStepRows: vi.fn() as Dispatch<SetStateAction<StepRow[]>>,
        setPipelineQueryType: vi.fn() as Dispatch<SetStateAction<PipelineQueryType | null>>,
        setTopic: vi.fn() as Dispatch<SetStateAction<string | null>>,
        setPipelineReasoning: vi.fn() as Dispatch<SetStateAction<string | null>>,
        streamRefs: buildStreamRefs(),
      }),
    );

    await act(async () => {
      await result.current.sendMessage('second');
    });

    expect(streamChat).toHaveBeenCalledWith('second', 'session-1', expect.any(Function));
    expect(getGenerationStatus).toHaveBeenCalledWith('session-1');
    expect(reconnectChatStream).toHaveBeenCalledWith('session-1', expect.any(Function));
    expect(finalizeAfterStreamClose).toHaveBeenCalled();
    expect(handleStreamEvents).toHaveBeenNthCalledWith(1, [token('A')], { renderMode: 'instant' });
    expect(handleStreamEvents).toHaveBeenNthCalledWith(2, [token('B')], { renderMode: 'realtime' });
  });
});
