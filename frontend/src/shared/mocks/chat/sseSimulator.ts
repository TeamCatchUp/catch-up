import { MOCK_RAG_ANSWER, MOCK_RELATED_JIRA_ISSUES,MOCK_SOURCES } from './data';

interface MockSSEOptions {
  sessionId: string;
  onMessage: (notification: RagNotification) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  stepDelay?: number;
}

const createMockSSE = (options: MockSSEOptions): EventSource => {
  const { sessionId, onMessage, onOpen, stepDelay = 500 } = options;

  const steps = ['router', 'rewrite', 'plan', 'retrieve', 'rerank', 'grade', 'generate'];
  let isClosed = false;
  let currentReadyState = 1; // OPEN
  const timers: ReturnType<typeof setTimeout>[] = [];

  // Mock EventSource 객체 (EventSource 인터페이스 호환)
  const mockEventSource = {
    get readyState() {
      return currentReadyState;
    },
    close: () => {
      isClosed = true;
      timers.forEach(clearTimeout);
      currentReadyState = 2; // CLOSED
      console.log('[MockSSE] 연결 종료');
    },
    url: 'mock://sse',
    withCredentials: false,
    onopen: null,
    onmessage: null,
    onerror: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
    CONNECTING: 0,
    OPEN: 1,
    CLOSED: 2,
  } as unknown as EventSource;

  // 시뮬레이션 시작
  const startTimer = setTimeout(() => {
    if (isClosed) return;

    console.log('[MockSSE] 연결 시작');
    onOpen?.();

    // CONNECT 이벤트
    onMessage({
      type: 'CONNECT',
      target: 'CHAT',
      message: 'Connected',
      data: null,
    });

    // 각 단계별 RAG_IN_PROGRESS
    steps.forEach((step, index) => {
      const timer = setTimeout(() => {
        if (isClosed) return;

        console.log(`[MockSSE] 단계 진행: ${step}`);

        onMessage({
          type: 'RAG_IN_PROGRESS',
          target: 'CHAT',
          message: null,
          data: {
            session_id: sessionId,
            type: 'status',
            node: step,
            message: `Processing ${step}...`,
          },
        });

        // 마지막 단계 후 RAG_DONE
        if (index === steps.length - 1) {
          const doneTimer = setTimeout(() => {
            if (isClosed) return;

            console.log('[MockSSE] RAG 완료');

            onMessage({
              type: 'RAG_DONE',
              target: 'CHAT',
              message: null,
              data: {
                session_id: sessionId,
                type: 'result',
                node: 'generate',
                response: {
                  session_id: sessionId,
                  answer: MOCK_RAG_ANSWER,
                  sources: MOCK_SOURCES as unknown as BackendSource[],
                  chat_history_id: `mock-history-${Date.now()}`,
                  has_feedback: false,
                },
                related_jira_issues: MOCK_RELATED_JIRA_ISSUES as unknown as BackendSource[],
              },
            });
          }, stepDelay);
          timers.push(doneTimer);
        }
      }, stepDelay * (index + 1));
      timers.push(timer);
    });
  }, 100);
  timers.push(startTimer);

  return mockEventSource;
};

export default createMockSSE;
