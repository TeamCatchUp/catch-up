import type { UserStatus } from '@/shared/queries/auth.types';

import { buildStreamingMockAnswer, MOCK_SOURCES } from './chat/data';
import { MOCK_JWT_TOKENS, MOCK_USER } from './auth/data';
import delay from './delay';
import { MOCK_FEEDBACK_RESPONSE } from './feedback/data';
import { MOCK_CHATROOMS, MOCK_RECENT_QUERIES, MOCK_RECENT_QUERIES_EMPTY } from './search/data';

const USE_EMPTY_RECENT_QUERIES = process.env.NEXT_PUBLIC_MOCK_RECENT_QUERIES_EMPTY === 'true';

type MockHandler = {
  pattern: RegExp;
  method: 'get' | 'post' | 'put' | 'delete';
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
    pattern: /^\/api\/chatrooms$/,
    method: 'get',
    handler: async () => MOCK_CHATROOMS,
  },
  {
    pattern: /^\/api\/chatrooms\/queries$/,
    method: 'get',
    handler: async () => (USE_EMPTY_RECENT_QUERIES ? MOCK_RECENT_QUERIES_EMPTY : MOCK_RECENT_QUERIES),
  },
  {
    pattern: /^\/api\/chatrooms\/[^/]+\/queries$/,
    method: 'get',
    handler: async () => (USE_EMPTY_RECENT_QUERIES ? MOCK_RECENT_QUERIES_EMPTY : MOCK_RECENT_QUERIES),
  },

  // Chat REST (SSE stream is mocked in chat/mockChatService.ts)
  {
    pattern: /^\/api\/chat$/,
    method: 'post',
    handler: async (_, data) => {
      const requestData = data as { query?: string } | undefined;
      const query = requestData?.query?.trim() || 'mock query';

      return {
        answer: buildStreamingMockAnswer(query),
        sources: MOCK_SOURCES,
        process_time: 0.31,
      };
    },
  },
  {
    pattern: /^\/api\/chat\/stream$/,
    method: 'post',
    handler: async () => ({
      message: 'SSE stream is not served by axios mock adapter. Use chatService.streamChat().',
    }),
  },
  {
    pattern: /^\/api\/chat\/stream\/resume$/,
    method: 'post',
    handler: async () => ({
      message: 'SSE resume is not served by axios mock adapter. Use chatService.resumeStream().',
    }),
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
        { id: '5b10ac8d14c9e6', name: 'Kim Dev', email: 'dev@catchup.io', picture: null },
        { id: '6a21bd9e25d0f7', name: 'Lee Dev', email: 'dev2@catchup.io', picture: null },
      ],
      github: [{ id: 'kimdev', name: 'Kim Dev', email: 'dev@catchup.io', picture: null }],
      slack: [{ id: 'U04ABC12DEF', name: 'Kim Dev', email: 'dev@catchup.io', picture: null }],
    }),
  },

  // Feedback
  {
    pattern: /^\/api\/chat\/feedback$/,
    method: 'post',
    handler: async (_, data) => {
      const requestData = data as { chat_history_id?: string; tags?: string[]; detail?: string } | undefined;
      return {
        ...MOCK_FEEDBACK_RESPONSE,
        chat_history_id: requestData?.chat_history_id || 'mock-history',
        tags: requestData?.tags || [],
        detail: requestData?.detail || '',
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
