import delay from '@/shared/mocks/delay';

const mockChatService = {
  streamChat: async (
    query: string,
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
    _signal?: AbortSignal,
  ) => {
    console.log('[mockChatService] streamChat:', { query, sessionId });

    await delay(500);
    onEvent({ type: 'status', node: 'router', message: '질문 분석 중...' });
    await delay(500);
    onEvent({ type: 'status', node: 'retrieve', message: '문서 검색 중...' });
    await delay(500);
    onEvent({ type: 'status', node: 'rerank', message: '관련도 평가 중...' });
    await delay(500);
    onEvent({ type: 'status', node: 'generate', message: '답변 생성 중...' });
    await delay(300);
    onEvent({
      type: 'result',
      answer: `Mock 답변: "${query}"에 대한 답변입니다.`,
      sources: [],
    });
  },

  resumeStream: async (
    sessionId: string,
    selectedPRs: { prNumber: number; repoName: string; owner: string }[],
    onEvent: (event: StreamEvent) => void,
    _signal?: AbortSignal,
  ) => {
    console.log('[mockChatService] resumeStream:', { sessionId, selectedPRs });

    await delay(500);
    onEvent({ type: 'status', node: 'generate', message: 'PR 컨텍스트로 답변 생성 중...' });
    await delay(500);
    onEvent({
      type: 'result',
      answer: `Mock 답변: PR ${selectedPRs.map((p) => p.prNumber).join(', ')} 기반 답변입니다.`,
      sources: [],
    });
  },
};

export default mockChatService;
