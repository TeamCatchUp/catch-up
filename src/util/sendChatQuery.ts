import { request } from 'node_modules/axios/index.cjs';
import api from 'src/api/axios';

// SSE 연결 생성
export const createSSEConection = (
  sessionId: string, // 추가
  onMessage: (notification: RagNotification) => void,
  onError?: (error: Event) => void,
  onOpen?: () => void,
): EventSource => {
  // const eventSource = new EventSource('https://0-0-0-0.example.io/api/notification/subscribe', {
  //   withCredentials: true,
  // });
  const url = 'https://0-0-0-0.example.io/api/notification/subscribe';

  const eventSource = new EventSource(url, {
    withCredentials: true,
  });

  eventSource.onopen = () => {
    console.log('[SSE] onopen');
    // console.log('[SSE] onopen, sessionId: ', sessionId);
    onOpen?.();
  };

  const safeParse = (event: MessageEvent) => {
    const raw = event.data;
    if (raw == null) return;

    const text = typeof raw === 'string' ? raw.trim() : raw;

    // keep-alive / 주석 라인 무시
    if (typeof text === 'string') {
      if (!text) return;
      if (text === ':') return;
      if (text.startsWith(':')) return;
    }

    // 1) JSON 파싱
    let parsed: unknown;
    try {
      parsed = typeof text === 'string' ? JSON.parse(text) : text;
    } catch (err) {
      console.error('[SSE] JSON parse error:', err, { eventType: event.type, raw });
      return;
    }

    // 2) 최소 형태 가드 (이상한 payload는 그냥 무시)
    if (!parsed || typeof parsed !== 'object' || !('type' in parsed) || !('target' in parsed)) {
      console.warn('[SSE] unknown payload ignored:', parsed);
      return;
    }

    // CONNECT 이벤트 로깅 (추가)
    if ((parsed as any).type === 'CONNECT') {
      console.log('[SSE] CONNECT event received: ', parsed);
    }

    // 3) onMessage 처리 에러 분리
    try {
      onMessage(parsed as RagNotification);
    } catch (err) {
      console.error('[SSE] onMessage handler error:', err, { notification: parsed });
    }
  };

  eventSource.addEventListener('CONNECT', safeParse as EventListener);
  eventSource.addEventListener('RAG_IN_PROGRESS', safeParse as EventListener);
  eventSource.addEventListener('RAG_INTERRUPT', safeParse as EventListener);
  eventSource.addEventListener('RAG_DONE', safeParse as EventListener);

  eventSource.onmessage = (event) => safeParse(event);

  eventSource.onerror = (event) => {
    console.error('[SSE] connection error:', event, 'readyState:', eventSource.readyState);
    onError?.(event);
  };

  return eventSource;
};

// 채팅 요청
export const sendChatQuery = async (
  queryText: string,
  sessionId: string,
  indexList: string[],
): Promise<ChatResponse> => {
  console.log('[sendChatQuery] 요청 전송: ', { queryText, sessionId, indexList });
  const requestBody = { query: queryText, sessionId, indexList };
  // const response = await api.post('/api/chat', requestBody);
  // return response.data;
  try {
    const response = await api.post('/api/chat', requestBody);
    console.log('[sendChatQuery] 응답 받음: ', response.data);

    // "SSE 연결이 필요합니다" 응답 체크
    if (response.data.answer === 'SSE 연결이 필요합니다.') {
      console.error('[sendChatQuery] SSE 연결 없음 - 백엔드가 SSE를 찾지 못함');
      throw new Error('SSE_NOT_CONNECTED');
    }
    return response.data;
  } catch (err) {
    console.error('[sendChatQuery] 에러: ', err);
    throw err;
  }
};

// 답변 생성 재개 요청
export const resumeChatQuery = async (
  sessionId: string,
  userSelectedPullRequests: { prNumber: number; repoName: string; owner: string }[],
): Promise<ChatResponse> => {
  const request: ResumeRequest = { sessionId, userSelectedPullRequests };
  const response = await api.post('/api/chat/resume', request);
  return response.data;
};
