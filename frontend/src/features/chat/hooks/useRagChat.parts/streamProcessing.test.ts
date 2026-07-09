import type { Dispatch, RefObject, SetStateAction } from 'react';
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ChatData, PipelineQueryType, StepRow, StreamEvent } from '@/features/chat/types';

import { useStreamProcessing } from './streamProcessing';
import type { ActiveStreamQuestion, SessionGuardRefs, StreamRuntimeRefs } from './types';

const buildChatData = (): ChatData => ({
  session_id: 'session-1',
  title: 'test',
  repo: '',
  messages: [
    {
      id: 'user-1',
      role: 'user',
      content: '질문',
      timestamp: '2026-01-01T00:00:00.000Z',
    },
    {
      id: 'assistant-1',
      role: 'assistant',
      content: '',
      timestamp: '2026-01-01T00:00:01.000Z',
    },
  ],
});

const token = (value: string): StreamEvent => ({
  type: 'token',
  session_id: 'session-1',
  token: value,
});

const ref = <T,>(current: T): RefObject<T> => ({ current });

const createState = <T,>(initialValue: T) => {
  let current = initialValue;
  const setter: Dispatch<SetStateAction<T>> = vi.fn((nextValue) => {
    current =
      typeof nextValue === 'function'
        ? (nextValue as (previousValue: T) => T)(current)
        : nextValue;
  });

  return {
    get current() {
      return current;
    },
    setter,
  };
};

const renderStreamProcessing = () => {
  const chatData = createState<ChatData | null>(buildChatData());
  const isLoading = createState(false);
  const isError = createState(false);
  const stepRows = createState<StepRow[]>([]);
  const pipelineQueryType = createState<PipelineQueryType | null>(null);
  const topic = createState<string | null>(null);
  const pipelineReasoning = createState<string | null>(null);

  const sessionRefs: SessionGuardRefs = {
    syncedSessionRef: ref<string | null>(null),
    sessionSyncGuardRef: ref<{ from: string; to: string } | null>(null),
    pendingReplaceSessionIdRef: ref<string | null>(null),
    hasPlaceholderReplacedRef: ref(false),
    canReplacePlaceholderRef: ref(false),
  };

  const streamRefs: StreamRuntimeRefs = {
    streamingMessageIdRef: ref<string | null>('assistant-1'),
    hasStreamedTokenRef: ref(false),
    latestSourcesRef: ref([]),
    latestUiSourcesRef: ref([]),
    streamInFlightRef: ref(false),
    hasAttemptedInitialStreamRef: ref(false),
    resolvedSessionIdRef: ref<string | undefined>('session-1'),
    activeQuestionRef: ref<ActiveStreamQuestion | null>(null),
  };

  const hook = renderHook(() =>
    useStreamProcessing({
      effectiveInitialQuery: null,
      resetStopped: vi.fn(),
      isStopped: () => false,
      resetStreamStateRefs: vi.fn(),
      syncChatDataFromServer: vi.fn(),
      refreshRecentChatsNow: vi.fn(),
      upsertOptimisticRecentChatNow: vi.fn(),
      resolveSessionIdFromStream: vi.fn(),
      stateSetters: {
        setChatData: chatData.setter,
        setIsLoading: isLoading.setter,
        setIsError: isError.setter,
        setStepRows: stepRows.setter,
        setPipelineQueryType: pipelineQueryType.setter,
        setTopic: topic.setter,
        setPipelineReasoning: pipelineReasoning.setter,
      },
      sessionRefs,
      streamRefs,
    }),
  );

  return { ...hook, chatData };
};

describe('useStreamProcessing renderMode', () => {
  it('instant replay는 연속 token 이벤트를 한 번의 chatData 업데이트로 반영한다', () => {
    const { result, chatData } = renderStreamProcessing();

    act(() => {
      result.current.handleStreamEvents([token('안'), token('녕')], { renderMode: 'instant' });
    });

    expect(chatData.current?.messages[1].content).toBe('안녕');
    expect(chatData.setter).toHaveBeenCalledTimes(1);
  });

  it('realtime은 token 이벤트 경계를 보존해 이벤트마다 chatData를 업데이트한다', () => {
    const { result, chatData } = renderStreamProcessing();

    act(() => {
      result.current.handleStreamEvents([token('안'), token('녕')], { renderMode: 'realtime' });
    });

    expect(chatData.current?.messages[1].content).toBe('안녕');
    expect(chatData.setter).toHaveBeenCalledTimes(2);
  });
});
