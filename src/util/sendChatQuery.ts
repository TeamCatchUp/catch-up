// import api from 'src/api/axios';

// // SSE 연결 생성
// export const createSSEConection = (
//   onMessage: (notification: RagNotification) => void,
//   onError?: (error: Event) => void,
//   onOpen?: () => void,
// ): EventSource => {
//   const eventSource = new EventSource('https://0-0-0-0.example.io/api/notification/subscribe', {
//     withCredentials: true,
//   });

//   eventSource.onopen = () => {
//     onOpen?.();
//   };

//   const safeParse = (event: MessageEvent) => {
//     const raw = event.data;
//     if (raw == null) return;

//     const text = typeof raw === 'string' ? raw.trim() : raw;
//     if (typeof text === 'string') {
//       if (!text) return;
//       if (text === ':') return;
//       if (text.startsWith(':')) return;
//     }

//     // 1) JSON 파싱 실패면 여기서 끝
//     let parsed: unknown;
//     try {
//       parsed = typeof text === 'string' ? JSON.parse(text) : text;
//     } catch (err) {
//       console.error('SSE JSON 파싱 에러:', err, 'raw:', raw, 'eventType:', event.type);
//       return;
//     }

//     if (!parsed || typeof parsed !== 'object' || !('type' in parsed) || !('target' in parsed)) {
//       console.warn('SSE unknown payload (ignored):', parsed);
//       return;
//     }

//     try {
//       onMessage(parsed as RagNotification);
//     } catch (err) {
//       console.error('SSE onMessage 처리 에러:', err, 'notification:', parsed);
//     }
//   };

//   // 서버가 event:xxx 로 보내는 "named event"들을 반드시 addEventListener로 받아야 함
//   eventSource.addEventListener('CONNECT', safeParse as EventListener);
//   eventSource.addEventListener('RAG_IN_PROGRESS', safeParse as EventListener);
//   eventSource.addEventListener('RAG_INTERRUPT', safeParse as EventListener);
//   eventSource.addEventListener('RAG_DONE', safeParse as EventListener);

//   eventSource.onmessage = (event) => safeParse(event);

//   eventSource.onerror = (event) => {
//     console.error('SSE 연결 에러:', event, 'readyState:', eventSource.readyState);
//     onError?.(event);
//   };

//   return eventSource;
// };

// // 채팅 요청
// export const sendChatQuery = async (
//   queryText: string,
//   sessionId: string,
//   indexList: string[],
// ): Promise<ChatResponse> => {
//   const requestBody = {
//     query: queryText,
//     sessionId: sessionId,
//     indexList,
//   };

//   try {
//     const response = await api.post('/api/chat', requestBody);
//     return response.data;
//   } catch (error) {
//     console.error('API 요청 중 에러 발생:', error);
//     throw error;
//   }
// };

// // 답변 생성 재개 요청
// export const resumeChatQuery = async (
//   sessionId: string,
//   userSelectedPullRequests: {
//     prNumber: number;
//     repoName: string;
//     owner: string;
//   }[],
// ): Promise<ChatResponse> => {
//   const request: ResumeRequest = {
//     sessionId,
//     userSelectedPullRequests,
//   };

//   try {
//     const response = await api.post('/api/chat/resume', request);
//     return response.data;
//   } catch (err) {
//     console.error('답변 재개 요청 중 에러 발생: ', err);
//     throw err;
//   }
// };

import api from 'src/api/axios';

// SSE 연결 생성
export const createSSEConection = (
  onMessage: (notification: RagNotification) => void,
  onError?: (error: Event) => void,
  onOpen?: () => void,
): EventSource => {
  const eventSource = new EventSource('https://0-0-0-0.example.io/api/notification/subscribe', {
    withCredentials: true,
  });

  eventSource.onopen = () => {
    console.log('[SSE] onopen');
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
  const requestBody = { query: queryText, sessionId, indexList };
  const response = await api.post('/api/chat', requestBody);
  return response.data;
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
