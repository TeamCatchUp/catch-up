import delay from '@/shared/mocks/delay';
import createMockSSE from './sseSimulator';

const mockChatService = {
  createSSEConnection: (
    sessionId: string,
    onMessage: (notification: RagNotification) => void,
    onError?: (error: Event) => void,
    onOpen?: () => void,
  ): EventSource => {
    console.log('[mockChatService] SSE 연결 생성:', sessionId);
    return createMockSSE({ sessionId, onMessage, onError, onOpen });
  },

  sendChatQuery: async (
    queryText: string,
    sessionId: string,
    indexList: string[],
  ): Promise<ChatResponse> => {
    console.log('[mockChatService] 채팅 요청:', { queryText, sessionId, indexList });
    await delay(200);
    return {
      sessionId,
      answer: '답변 생성을 시작합니다.',
      sources: [],
    };
  },

  resumeChatQuery: async (
    sessionId: string,
    userSelectedPullRequests: { prNumber: number; repoName: string; owner: string }[],
  ): Promise<ChatResponse> => {
    console.log('[mockChatService] 채팅 재개:', { sessionId, userSelectedPullRequests });
    await delay(200);
    return {
      sessionId,
      answer: '답변 생성을 재개합니다.',
      sources: [],
    };
  },
};

export default mockChatService;
