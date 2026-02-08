// Data imports
import { MOCK_JWT_TOKENS,MOCK_USER } from './auth/data';
import delay from './delay';
import { MOCK_FEEDBACK_RESPONSE } from './feedback/data';
import { DEFAULT_FILE_TREE,MOCK_FILE_TREES, MOCK_REPOSITORIES } from './github/data';
import { MOCK_CHATROOMS, MOCK_JIRA_TICKETS,MOCK_RECENT_QUERIES } from './search/data';

type MockHandler = {
  pattern: RegExp;
  method: 'get' | 'post' | 'put' | 'delete';
  handler: (url: string, data?: unknown) => Promise<unknown>;
};

/**
 * Mock 핸들러 목록
 * - pattern: URL 매칭용 정규식
 * - method: HTTP 메서드
 * - handler: Mock 데이터 반환 함수
 */
const mockHandlers: MockHandler[] = [
  // ═══════════════════════════════════════
  // Auth
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/v1\/auth\/me$/,
    method: 'get',
    handler: async () => MOCK_USER,
  },
  {
    pattern: /^\/api\/v1\/auth\/logout$/,
    method: 'post',
    handler: async () => ({ success: true }),
  },
  {
    pattern: /^\/api\/v1\/auth\/refresh$/,
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
  {
    pattern: /^\/api\/chatrooms\/[^/]+\/queries$/,
    method: 'get',
    handler: async () => MOCK_RECENT_QUERIES,
  },

  // ═══════════════════════════════════════
  // GitHub
  // ═══════════════════════════════════════
  {
    pattern: /^\/api\/v1\/github\/installations$/,
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
    pattern: /^\/api\/chat\/stream\/resume$/,
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

/**
 * 요청 URL과 메서드에 맞는 Mock 핸들러 찾기
 * mockHandlers 배열을 순회하며 pattern.test(url)로 매칭
 */
export const findMockHandler = (method: string, url: string): MockHandler | undefined => {
  return mockHandlers.find(
    (h) => h.method === method.toLowerCase() && h.pattern.test(url)
  );
};

/**
 * Mock 응답 생성 함수 (axios interceptor에서 호출)
 *
 * 동작 흐름:
 * 1. findMockHandler로 URL/메서드에 맞는 핸들러 검색
 * 2. 핸들러가 없으면 null 반환 → 실제 API 호출로 진행
 * 3. 핸들러가 있으면 100-300ms 지연 후 Mock 데이터 반환
 *
 * @param method - HTTP 메서드 (get, post 등)
 * @param url - 요청 URL (/api/me 등)
 * @param data - POST 요청 시 body 데이터
 * @returns Mock 응답 { data, status } 또는 null
 */
export const createMockResponse = async (
  method: string,
  url: string,
  data?: unknown
): Promise<{ data: unknown; status: number } | null> => {
  const handler = findMockHandler(method, url);
  if (!handler) return null;

  // 실제 API처럼 보이도록 랜덤 지연
  await delay(100 + Math.random() * 200);

  const mockData = await handler.handler(url, data);
  return { data: mockData, status: 200 };
};

export default mockHandlers;
