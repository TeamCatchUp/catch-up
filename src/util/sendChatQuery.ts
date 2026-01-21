import api from 'src/api/axios';

// SSE 연결 생성
export const createSSEConection = (
  onMessage: (notification: RagNotification) => void,
  onError?: (error: Event) => void,
): EventSource => {
  const eventSource = new EventSource('https://0-0-0-0.example.io/api/notification/subscribe', {
    withCredentials: true,
  });

  const safeParse = (event: MessageEvent) => {
    try {
      const notification: RagNotification = JSON.parse(event.data);
      onMessage(notification);
    } catch (err) {
      console.error('SSE 메시지 파싱 에러:', err, 'raw:', event.data);
    }
  };

  // 서버가 event:xxx 로 보내는 "named event"들을 반드시 addEventListener로 받아야 함
  eventSource.addEventListener('CONNECT', safeParse as EventListener);
  eventSource.addEventListener('RAG_IN_PROGRESS', safeParse as EventListener);
  eventSource.addEventListener('RAG_INTERRUPT', safeParse as EventListener);
  eventSource.addEventListener('RAG_DONE', safeParse as EventListener);

  eventSource.onmessage = (event) => {
    try {
      const notification: RagNotification = JSON.parse(event.data);
      onMessage(notification);
    } catch (err) {
      console.error('SSE 메시지 파싱 에러:', err);
    }
  };

  // eventSource.onerror = (event) => {
  //   // console.error('SSE 연결 에러:', event);
  //   // if (onError) {
  //   //   onError(event);
  //   // }
  //   console.error('SSE error. readyState=', eventSource.readyState, event);

  //   if (eventSource.readyState === EventSource.CLOSED) {
  //     onError?.(event); // 진짜로 끊긴 경우에만
  //   }
  // };
  eventSource.onerror = (event) => {
    console.error('SSE 연결 에러:', event, 'readyState:', eventSource.readyState);
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
  const requestBody = {
    query: queryText,
    sessionId: sessionId,
    indexList,
  };

  try {
    const response = await api.post('/api/chat', requestBody);
    return response.data;
  } catch (error) {
    console.error('API 요청 중 에러 발생:', error);
    throw error;
  }
};

// 답변 생성 재개 요청
export const resumeChatQuery = async (
  sessionId: string,
  userSelectedPullRequests: {
    prNumber: number;
    repoName: string;
    owner: string;
  }[],
): Promise<ChatResponse> => {
  const request: ResumeRequest = {
    sessionId,
    userSelectedPullRequests,
  };

  try {
    const response = await api.post('/api/chat/resume', request);
    return response.data;
  } catch (err) {
    console.error('답변 재개 요청 중 에러 발생: ', err);
    throw err;
  }
};
