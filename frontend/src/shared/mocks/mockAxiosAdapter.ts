import { MOCK_ENTRY_REQUESTS } from './admin/adminMembersMockData';
import { MOCK_JWT_TOKENS, MOCK_USER } from './auth/data';
import delay from './delay';
import { MOCK_FEEDBACK_RESPONSE } from './feedback/data';
import { MOCK_CHATROOM_MESSAGES, MOCK_CHATROOMS, MOCK_RECENT_QUERIES, MOCK_RECENT_QUERIES_EMPTY } from './search/data';

const USE_EMPTY_RECENT_QUERIES = process.env.NEXT_PUBLIC_MOCK_RECENT_QUERIES_EMPTY === 'true';

type MockHandler = {
  pattern: RegExp;
  method: 'get' | 'post' | 'put' | 'delete' | 'patch';
  handler: (url: string, data?: unknown) => Promise<unknown>;
};

const mockHandlers: MockHandler[] = [
  // Auth
  {
    pattern: /^\/api\/v1\/auth\/me$/,
    method: 'get',
    handler: async () => MOCK_USER,
  },
  {
    pattern: /^\/api\/v1\/auth\/me\/profile$/,
    method: 'get',
    handler: async () => ({
      name: MOCK_USER.name,
      email: MOCK_USER.email,
      picture: MOCK_USER.picture ?? '',
      department: '사업개발팀',
      job_level: 'member',
    }),
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

  // Chatrooms
  {
    pattern: /^\/api\/v1\/rooms$/,
    method: 'get',
    handler: async () => MOCK_CHATROOMS,
  },
  {
    pattern: /^\/api\/v1\/rooms\/queries$/,
    method: 'get',
    handler: async () => (USE_EMPTY_RECENT_QUERIES ? MOCK_RECENT_QUERIES_EMPTY : MOCK_RECENT_QUERIES),
  },
  {
    pattern: /^\/api\/v1\/rooms\/[^/]+\/queries$/,
    method: 'get',
    handler: async () => (USE_EMPTY_RECENT_QUERIES ? MOCK_RECENT_QUERIES_EMPTY : MOCK_RECENT_QUERIES),
  },
  {
    pattern: /^\/api\/v1\/rooms\/[^/]+\/messages$/,
    method: 'get',
    handler: async (url) => {
      const matched = url.match(/^\/api\/v1\/rooms\/([^/]+)\/messages$/);
      const sessionId = matched?.[1] ?? MOCK_CHATROOM_MESSAGES.session_id;
      return {
        ...MOCK_CHATROOM_MESSAGES,
        session_id: sessionId,
      };
    },
  },

  // Chat (SSE stream is mocked in chat/mockChatService.ts)
  {
    pattern: /^\/api\/v1\/chat\/stream$/,
    method: 'post',
    handler: async () => ({
      message: 'SSE stream is not served by axios mock adapter. Use chatService.streamChat().',
    }),
  },
  // TODO: resume API 백엔드 구현 시 재활성
  // {
  //   pattern: /^\/api\/v1\/chat\/stream\/resume$/,
  //   method: 'post',
  //   handler: async () => ({
  //     message: 'SSE resume is not served by axios mock adapter. Use chatService.resumeStream().',
  //   }),
  // },
  // reset-last
  {
    pattern: /^\/api\/v1\/chat\/[^/]+\/reset-last$/,
    method: 'post',
    handler: async () => ({ status: 'success', deleted_query: 'mock deleted query' }),
  },

  // Integration status
  {
    pattern: /^\/api\/v1\/jira\/sync\/status$/,
    method: 'get',
    handler: async () => [
      { entity_type: 'issue', last_successful_sync_at: '2026-02-15T10:30:00Z', status: 'completed' },
    ],
  },
  {
    pattern: /^\/api\/v1\/auth\/slack\/status$/,
    method: 'get',
    handler: async () => ({
      workspaces: [{ team_id: 'T04MOCK001', team_name: 'CatchUp Workspace' }],
    }),
  },
  {
    pattern: /^\/api\/v1\/github\/installations$/,
    method: 'get',
    handler: async () => [{ id: 12345678, account: { login: 'catchup-org' }, app_slug: 'catchup-bot' }],
  },

  // Onboarding — 일반 유저 가입
  {
    pattern: /^\/api\/v1\/onboarding$/,
    method: 'post',
    handler: async (_, data) => {
      MOCK_USER.status = 'active';
      const req = data as { name?: string; job_level?: string; department?: string } | undefined;
      return {
        id: 1,
        email: MOCK_USER.email,
        name: req?.name ?? MOCK_USER.name,
        department: req?.department ?? '',
        job_level: req?.job_level ?? 'member',
        provider: 'keycloak',
      };
    },
  },
  // Onboarding — 어드민 가입
  {
    pattern: /^\/api\/v1\/onboarding\/admin$/,
    method: 'post',
    handler: async (_, data) => {
      MOCK_USER.status = 'active';
      const req = data as { name?: string; job_level?: string; company_name?: string } | undefined;
      return {
        id: 1,
        email: MOCK_USER.email,
        name: req?.name ?? MOCK_USER.name,
        department: req?.company_name ?? '',
        job_level: req?.job_level ?? 'executive',
        provider: 'keycloak',
      };
    },
  },

  // Admin — 입장 신청
  {
    pattern: /^\/api\/v1\/admin\/members\/requests$/,
    method: 'get',
    handler: async () => MOCK_ENTRY_REQUESTS,
  },
  {
    pattern: /^\/api\/v1\/admin\/members\/requests\/decide$/,
    method: 'post',
    handler: async () => {
      return { success: true };
    },
  },

  // Feedback (PATCH /api/v1/rooms/{sessionId}/messages/{messageId}/feedback)
  {
    pattern: /^\/api\/v1\/rooms\/[^/]+\/messages\/[^/]+\/feedback$/,
    method: 'patch',
    handler: async (_, data) => {
      const requestData = data as { is_liked?: boolean | null; reasons?: string[]; comment?: string } | undefined;
      return {
        ...MOCK_FEEDBACK_RESPONSE,
        is_liked: requestData?.is_liked ?? null,
      };
    },
  },
];

export const findMockHandler = (method: string, url: string): MockHandler | undefined => {
  return mockHandlers.find((handler) => handler.method === method.toLowerCase() && handler.pattern.test(url));
};

export const createMockResponse = async (
  method: string,
  url: string,
  data?: unknown,
): Promise<{ data: unknown; status: number } | null> => {
  const handler = findMockHandler(method, url);
  if (!handler) return null;

  await delay(100 + Math.random() * 200);
  const mockData = await handler.handler(url, data);
  return { data: mockData, status: 200 };
};

export default mockHandlers;
