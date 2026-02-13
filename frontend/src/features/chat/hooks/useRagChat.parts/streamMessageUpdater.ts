import type { ChatData, ChatSource, Message } from '@/features/chat/types';

interface AppendStreamingTokenParams {
  prev: ChatData;
  token: string;
  currentStreamingMessageId: string | null;
  latestUiSources: ChatSource[];
  effectiveInitialQuery: string | null;
}

interface UpdateStreamingSourcesParams {
  prev: ChatData;
  currentStreamingMessageId: string | null;
  latestUiSources: ChatSource[];
}

interface StreamingUpdateResult {
  nextData: ChatData;
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
 */
export const updateStreamingSources = ({
  prev,
  currentStreamingMessageId,
  latestUiSources,
}: UpdateStreamingSourcesParams): StreamingUpdateResult => {
  let resolvedStreamingMessageId = currentStreamingMessageId;
  if (!resolvedStreamingMessageId) {
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
