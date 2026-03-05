import type { ChatData, ChatSource, Message } from '@/features/chat/types';

const CITATION_PATTERN = /\[(\d+)\]/g;

/**
 * assistant 답변 본문의 인용 패턴 [N]을 기반으로 is_cited를 유도
 * - 이미 is_cited: true인 source가 하나라도 있으면(서버가 설정한 경우) 해당 메시지는 건너뜀
 * - 백엔드가 source_candidates 이벤트에서 is_cited를 보내지 않아 false로 남는 문제를 해결
 */
export const deriveCitedFromAnswerContent = (messages: Message[]): Message[] => {
  let changed = false;
  const result = messages.map((msg) => {
    if (msg.role !== 'assistant' || !msg.sources?.length) return msg;
    if (msg.sources.some((s) => s.is_cited)) return msg;

    const citedIndices = new Set<number>();
    for (const match of msg.content.matchAll(CITATION_PATTERN)) {
      citedIndices.add(Number(match[1]));
    }
    if (citedIndices.size === 0) return msg;

    changed = true;
    return {
      ...msg,
      sources: msg.sources.map((s) => ({
        ...s,
        is_cited: citedIndices.has(s.source_index),
      })),
    };
  });
  return changed ? result : messages;
};

interface AppendStreamingTokenParams {
  // 기존 chatData 스냅샷
  prev: ChatData;
  // 이번 이벤트에서 들어온 토큰 1개
  token: string;
  // 현재 스트리밍 대상 assistant 메시지 id
  currentStreamingMessageId: string | null;
  // 최신 UI용 sources(정규화 완료)
  latestUiSources: ChatSource[];
  // 첫 질문 자동실행 케이스에서 user 메시지 보정용
  effectiveInitialQuery: string | null;
}

interface UpdateStreamingSourcesParams {
  prev: ChatData;
  currentStreamingMessageId: string | null;
  latestUiSources: ChatSource[];
}

interface StreamingUpdateResult {
  // 업데이트된 chatData
  nextData: ChatData;
  // 다음 토큰이 붙어야 할 메시지 id
  nextStreamingMessageId: string | null;
}

/**
 * 토큰 1개를 스트리밍 메시지에 누적 반영
 * - 기존 스트리밍 메시지가 있으면 해당 메시지에 append
 * - 없으면 마지막 assistant 메시지에 append
 * - assistant 메시지도 없으면 새 assistant 메시지 생성
 */
export const appendStreamingToken = ({
  prev,
  token,
  currentStreamingMessageId,
  latestUiSources,
  effectiveInitialQuery,
}: AppendStreamingTokenParams): StreamingUpdateResult => {
  // 1) 이미 스트리밍 대상 메시지를 알고 있으면, 해당 메시지에 직접 append
  if (currentStreamingMessageId) {
    const streamMessageIndex = prev.messages.findIndex((message) => message.id === currentStreamingMessageId);

    if (streamMessageIndex >= 0) {
      const messages = [...prev.messages];
      const currentMessage = messages[streamMessageIndex];
      messages[streamMessageIndex] = {
        ...currentMessage,
        content: `${currentMessage.content}${token}`,
        sources: latestUiSources,
        detailed_tasks: currentMessage.detailed_tasks ?? [],
      };
      return {
        nextData: { ...prev, messages },
        nextStreamingMessageId: currentStreamingMessageId,
      };
    }
  }

  // 2) 명시 id는 없지만 마지막 메시지가 assistant면 거기에 이어 붙임
  const lastMessage = prev.messages[prev.messages.length - 1];
  if (lastMessage?.role === 'assistant') {
    const messages = [...prev.messages];
    messages[messages.length - 1] = {
      ...lastMessage,
      content: `${lastMessage.content}${token}`,
      sources: latestUiSources,
      detailed_tasks: lastMessage.detailed_tasks ?? [],
    };
    return {
      nextData: { ...prev, messages },
      nextStreamingMessageId: lastMessage.id,
    };
  }

  // 3) assistant 메시지가 전혀 없는 경우:
  //    필요하면 user 메시지를 먼저 보정해 넣고, 새 assistant 메시지를 생성
  const hasUser = prev.messages.some((message) => message.role === 'user');
  const baseMessages = [...prev.messages];
  if (!hasUser && effectiveInitialQuery) {
    baseMessages.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: effectiveInitialQuery,
      timestamp: new Date().toISOString(),
    });
  }

  const messageId = crypto.randomUUID();
  const assistantMessage: Message = {
    id: messageId,
    role: 'assistant',
    content: token,
    sources: latestUiSources,
    detailed_tasks: [],
    timestamp: new Date().toISOString(),
  };

  return {
    nextData: {
      ...prev,
      messages: [...baseMessages, assistantMessage],
    },
    nextStreamingMessageId: messageId,
  };
};

/**
 * 스트리밍 중인 메시지의 sources만 갱신
 *
 * 동작:
 * - 명시된 streaming id가 있으면 해당 메시지 갱신
 * - 없으면 마지막 assistant 메시지를 대상 메시지로 추론
 * - 대상을 못 찾으면 기존 데이터 그대로 반환
 */
export const updateStreamingSources = ({
  prev,
  currentStreamingMessageId,
  latestUiSources,
}: UpdateStreamingSourcesParams): StreamingUpdateResult => {
  let resolvedStreamingMessageId = currentStreamingMessageId;
  if (!resolvedStreamingMessageId) {
    // 토큰 시작 전에 sources가 먼저 오는 케이스를 위해 마지막 assistant를 fallback으로 사용
    const lastMessage = prev.messages[prev.messages.length - 1];
    if (lastMessage?.role === 'assistant') {
      resolvedStreamingMessageId = lastMessage.id;
    }
  }

  if (!resolvedStreamingMessageId) {
    return {
      nextData: prev,
      nextStreamingMessageId: currentStreamingMessageId,
    };
  }

  const streamMessageIndex = prev.messages.findIndex((message) => message.id === resolvedStreamingMessageId);
  if (streamMessageIndex < 0) {
    return {
      nextData: prev,
      nextStreamingMessageId: resolvedStreamingMessageId,
    };
  }

  const messages = [...prev.messages];
  const currentMessage = messages[streamMessageIndex];
  messages[streamMessageIndex] = {
    ...currentMessage,
    sources: latestUiSources,
  };

  return {
    nextData: { ...prev, messages },
    nextStreamingMessageId: resolvedStreamingMessageId,
  };
};
