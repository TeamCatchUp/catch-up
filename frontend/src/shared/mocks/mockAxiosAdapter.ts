import type { UserStatus } from '@/shared/queries/auth.types';

import { MOCK_ADMIN_MEMBERS, MOCK_ENTRY_REQUESTS } from './admin/adminMembersMockData';
import { MOCK_JWT_TOKENS, MOCK_USER } from './auth/data';
import delay from './delay';
import { MOCK_FEEDBACK_RESPONSE } from './feedback/data';
import { MOCK_CHATROOMS, MOCK_RECENT_QUERIES, MOCK_RECENT_QUERIES_EMPTY } from './search/data';

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
    pattern: /^\/api\/v1\/auth\/jira\/status$/,
    method: 'get',
    handler: async () => ({
      resources: [{ id: 'mock-cloud-id-001', name: 'CatchUp Jira', url: 'https://catchup.atlassian.net' }],
    }),
  },
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

  // Onboarding
  {
    pattern: /^\/api\/v1\/onboarding\/complete$/,
    method: 'post',
    handler: async (_, data) => {
      console.log('[Mock] onboarding complete:', data);
      const nextStatus: UserStatus = MOCK_USER.role === 'admin' ? 'active' : 'pending';
      MOCK_USER.status = nextStatus;
      return { success: true };
    },
  },
  {
    pattern: /^\/api\/v1\/onboarding\/connectors$/,
    method: 'get',
    handler: async () => ({
      jira: [
        { id: 'jira-kimdev', name: 'Kim Dev', email: 'dev1@catchup.io', picture: null },
        { id: 'jira-leedev', name: 'Lee Dev', email: 'dev2@catchup.io', picture: null },
        { id: 'jira-parkdev', name: 'Park Dev', email: 'dev3@catchup.io', picture: null },
        { id: 'jira-choidev', name: 'Choi Dev', email: 'dev4@catchup.io', picture: null },
        { id: 'jira-jungdev', name: 'Jung Dev', email: 'dev5@catchup.io', picture: null },
        { id: 'jira-handev', name: 'Han Dev', email: 'dev6@catchup.io', picture: null },
        { id: 'jira-limdev', name: 'Lim Dev', email: 'dev7@catchup.io', picture: null },
        { id: 'jira-yoondev', name: 'Yoon Dev', email: 'dev8@catchup.io', picture: null },
        { id: 'jira-jangdev', name: 'Jang Dev', email: 'dev9@catchup.io', picture: null },
        { id: 'jira-kangdev', name: 'Kang Dev', email: 'dev10@catchup.io', picture: null },
        { id: 'jira-shindev', name: 'Shin Dev', email: 'dev11@catchup.io', picture: null },
        { id: 'jira-chodev', name: 'Cho Dev', email: 'dev12@catchup.io', picture: null },
      ],
      github: [
        { id: 'kimdev', name: 'Kim Dev', email: 'dev1@catchup.io', picture: null },
        { id: 'parkdev', name: 'Park Dev', email: 'dev3@catchup.io', picture: null },
        { id: 'jungdev', name: 'Jung Dev', email: 'dev5@catchup.io', picture: null },
      ],
      slack: [
        { id: 'U04ABC12DEF', name: 'Kim Dev', email: 'dev1@catchup.io', picture: null },
        { id: 'U04PARK03XYZ', name: 'Park Dev', email: 'dev3@catchup.io', picture: null },
        { id: 'U04JUNG05XYZ', name: 'Jung Dev', email: 'dev5@catchup.io', picture: null },
      ],
    }),
  },

  // Admin — 이용자 관리
  {
    pattern: /^\/api\/v1\/admin\/members$/,
    method: 'get',
    handler: async () => MOCK_ADMIN_MEMBERS,
  },
  {
    pattern: /^\/api\/v1\/admin\/members\/requests$/,
    method: 'get',
    handler: async () => MOCK_ENTRY_REQUESTS,
  },
  {
    pattern: /^\/api\/v1\/admin\/members\/requests\/decide$/,
    method: 'post',
    handler: async (_, data) => {
      console.log('[Mock] member request decision:', data);
      return { success: true };
    },
  },
  {
    pattern: /^\/api\/v1\/admin\/members\/[^/]+\/status$/,
    method: 'patch',
    handler: async (_, data) => {
      console.log('[Mock] member status change:', data);
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
