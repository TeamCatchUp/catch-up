import delay from './delay';

// Data imports
import { MOCK_USER, MOCK_JWT_TOKENS } from './auth/data';
import { MOCK_CHATROOMS, MOCK_RECENT_QUERIES, MOCK_JIRA_TICKETS } from './search/data';
import { MOCK_REPOSITORIES, MOCK_FILE_TREES, DEFAULT_FILE_TREE } from './github/data';
import { MOCK_FEEDBACK_RESPONSE } from './feedback/data';

type MockHandler = {
  pattern: RegExp;
  method: 'get' | 'post' | 'put' | 'delete';
  handler: (url: string, data?: unknown) => Promise<unknown>;
};

const mockHandlers: MockHandler[] = [
  // ═══════════════════════════════════════
  // Auth
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/me$/,
    method: 'get',
    handler: async () => MOCK_USER,
  },
  {
    pattern: /^\/api\/auth\/logout$/,
    method: 'post',
    handler: async () => ({ success: true }),
  },
  {
    pattern: /^\/api\/auth\/refresh$/,
    method: 'post',
    handler: async () => MOCK_JWT_TOKENS,
  },

  // ═══════════════════════════════════════
  // Chatrooms
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/chatrooms$/,
    method: 'get',
    handler: async () => MOCK_CHATROOMS,
  },
  {
    pattern: /^\/api\/chatrooms\/queries$/,
    method: 'get',
    handler: async () => MOCK_RECENT_QUERIES,
  },

  // ═══════════════════════════════════════
  // GitHub
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/github\/read\/repositories$/,
    method: 'get',
    handler: async () => MOCK_REPOSITORIES,
  },
  {
    pattern: /^\/api\/github\/read\/repositories\/(\d+)\/files$/,
    method: 'get',
    handler: async (url) => {
      // URL에서 repoId 추출: /api/github/read/repositories/123/files
      const match = url.match(/\/api\/github\/read\/repositories\/(\d+)\/files/);
      const repoId = match ? parseInt(match[1], 10) : 0;
      return MOCK_FILE_TREES[repoId] || DEFAULT_FILE_TREE;
    },
  },

  // ═══════════════════════════════════════
  // Jira
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/jira\/issues$/,
    method: 'get',
    handler: async () => MOCK_JIRA_TICKETS,
  },

  // ═══════════════════════════════════════
  // Chat (REST 부분만 - SSE는 서비스 레이어)
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/chat$/,
    method: 'post',
    handler: async (_, data) => {
      const requestData = data as { sessionId?: string } | undefined;
      return {
        sessionId: requestData?.sessionId || 'mock-session',
        answer: '답변 생성을 시작합니다.',
        sources: [],
      };
    },
  },
  {
    pattern: /^\/api\/chat\/resume$/,
    method: 'post',
    handler: async (_, data) => {
      const requestData = data as { sessionId?: string } | undefined;
      return {
        sessionId: requestData?.sessionId || 'mock-session',
        answer: '답변 생성을 재개합니다.',
        sources: [],
      };
    },
  },

  // ═══════════════════════════════════════
  // Feedback
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/chat\/feedback$/,
    method: 'post',
    handler: async (_, data) => {
      const requestData = data as { chatHistoryId?: string; tags?: string[]; detail?: string } | undefined;
      return {
        ...MOCK_FEEDBACK_RESPONSE,
        chatHistoryId: requestData?.chatHistoryId || 'mock-history',
        tags: requestData?.tags || [],
        detail: requestData?.detail || '',
      };
    },
  },
];

export const findMockHandler = (method: string, url: string): MockHandler | undefined => {
  return mockHandlers.find(
    (h) => h.method === method.toLowerCase() && h.pattern.test(url)
  );
};

// Mock 응답을 생성하는 헬퍼 함수
export const createMockResponse = async (
  method: string,
  url: string,
  data?: unknown
): Promise<{ data: unknown; status: number } | null> => {
  const handler = findMockHandler(method, url);
  if (!handler) return null;

  // API 지연 시뮬레이션 (100-300ms)
  await delay(100 + Math.random() * 200);

  const mockData = await handler.handler(url, data);
  return { data: mockData, status: 200 };
};

export default mockHandlers;
