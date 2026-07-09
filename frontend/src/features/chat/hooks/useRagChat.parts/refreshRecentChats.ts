import type { InfiniteData, QueryClient } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import type {
  ChatroomResponse,
  ChatroomsResponse,
  RecentQueriesResponse,
  RecentQueryResponse,
} from '@/shared/types/query/api';

import type { ActiveStreamQuestion } from './types';

const HISTORY_PAGE_SIZE = 50;

interface OptimisticRecentChatInput extends ActiveStreamQuestion {
  sessionId: string;
}

/**
 * 최근 채팅/질문 목록을 갱신
 * - 사이드바 리프레시 커스텀 이벤트 발생
 * - TanStack Query 캐시 무효화
 *
 * - 일부 컴포넌트는 window 이벤트로만 갱신을 감지
 * - 일부 컴포넌트는 React Query 캐시 무효화로 갱신
 * -> 두 경로를 함께 호출해 UI 동기화를 확실히 맞춘다.
 */
export const refreshRecentChats = (queryClient: QueryClient) => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('refresh_sidebar'));
  }
  void queryClient.invalidateQueries({ queryKey: chatQueries.lists() });
};

const createRecentQueryItem = ({
  sessionId,
  content,
  createdAt,
  tempId,
}: OptimisticRecentChatInput): RecentQueryResponse => ({
  id: tempId,
  session_id: sessionId,
  content,
  created_at: createdAt,
});

const createRecentQueriesPage = (input: OptimisticRecentChatInput): RecentQueriesResponse => ({
  total: 1,
  page: 1,
  size: HISTORY_PAGE_SIZE,
  items: [createRecentQueryItem(input)],
});

const upsertRecentQueryPage = (
  page: RecentQueriesResponse,
  input: OptimisticRecentChatInput,
): RecentQueriesResponse => {
  const nextItem = createRecentQueryItem(input);
  const hadItem = page.items.some((item) => item.id === input.tempId);
  const nextItems = [nextItem, ...page.items.filter((item) => item.id !== input.tempId)];

  return {
    ...page,
    total: hadItem ? page.total : page.total + 1,
    items: nextItems.slice(0, page.size || HISTORY_PAGE_SIZE),
  };
};

const upsertRecentQueryInfiniteData = (
  old: InfiniteData<RecentQueriesResponse> | undefined,
  input: OptimisticRecentChatInput,
): InfiniteData<RecentQueriesResponse> => {
  if (!old?.pages.length) {
    return { pages: [createRecentQueriesPage(input)], pageParams: [1] };
  }

  const hadItem = old.pages.some((page) => page.items.some((item) => item.id === input.tempId));
  const nextItem = createRecentQueryItem(input);
  const totalDelta = hadItem ? 0 : 1;
  const nextItems = [
    nextItem,
    ...old.pages.flatMap((page) => page.items).filter((item) => item.id !== input.tempId),
  ];
  let cursor = 0;

  return {
    ...old,
    pages: old.pages.map((page, index) => {
      const pageSize = page.size || HISTORY_PAGE_SIZE;
      const items =
        index === old.pages.length - 1 ? nextItems.slice(cursor) : nextItems.slice(cursor, cursor + pageSize);
      cursor += items.length;

      return {
        ...page,
        total: page.total + totalDelta,
        items,
      };
    }),
  };
};

const createChatroomItem = ({ sessionId, content, createdAt }: OptimisticRecentChatInput): ChatroomResponse => ({
  session_id: sessionId,
  title: content,
  created_at: createdAt,
  updated_at: createdAt,
});

const upsertChatroomPage = (page: ChatroomsResponse, input: OptimisticRecentChatInput): ChatroomsResponse => {
  const existing = page.items.find((item) => item.session_id === input.sessionId);
  const nextItem = existing ? { ...existing, updated_at: input.createdAt } : createChatroomItem(input);
  const nextItems = [nextItem, ...page.items.filter((item) => item.session_id !== input.sessionId)];

  return {
    ...page,
    total: existing ? page.total : page.total + 1,
    items: nextItems.slice(0, page.size || HISTORY_PAGE_SIZE),
  };
};

const upsertChatroomInfiniteData = (
  old: InfiniteData<ChatroomsResponse> | undefined,
  input: OptimisticRecentChatInput,
): InfiniteData<ChatroomsResponse> => {
  if (!old?.pages.length) {
    return {
      pages: [
        {
          total: 1,
          page: 1,
          size: HISTORY_PAGE_SIZE,
          items: [createChatroomItem(input)],
        },
      ],
      pageParams: [1],
    };
  }

  const existing = old.pages.flatMap((page) => page.items).find((item) => item.session_id === input.sessionId);
  const nextItem = existing ? { ...existing, updated_at: input.createdAt } : createChatroomItem(input);
  const totalDelta = existing ? 0 : 1;
  const nextItems = [
    nextItem,
    ...old.pages.flatMap((page) => page.items).filter((item) => item.session_id !== input.sessionId),
  ];
  let cursor = 0;

  return {
    ...old,
    pages: old.pages.map((page, index) => {
      const pageSize = page.size || HISTORY_PAGE_SIZE;
      const items =
        index === old.pages.length - 1 ? nextItems.slice(cursor) : nextItems.slice(cursor, cursor + pageSize);
      cursor += items.length;

      return {
        ...page,
        total: page.total + totalDelta,
        items,
      };
    }),
  };
};

export const upsertOptimisticRecentChat = (queryClient: QueryClient, input: OptimisticRecentChatInput) => {
  const content = input.content.trim();
  if (!input.sessionId || !content) return;

  const normalizedInput = { ...input, content };

  queryClient.setQueryData<RecentQueriesResponse>(chatQueries.recentQueries().queryKey, (old) =>
    old ? upsertRecentQueryPage(old, normalizedInput) : createRecentQueriesPage(normalizedInput),
  );
  queryClient.setQueryData<InfiniteData<RecentQueriesResponse>>(chatQueries.recentQueriesInfinite().queryKey, (old) =>
    upsertRecentQueryInfiniteData(old, normalizedInput),
  );
  queryClient.setQueryData<ChatroomsResponse>(chatQueries.recentRooms().queryKey, (old) =>
    old
      ? upsertChatroomPage(old, normalizedInput)
      : upsertChatroomPage({ total: 0, page: 1, size: HISTORY_PAGE_SIZE, items: [] }, normalizedInput),
  );
  queryClient.setQueryData<InfiniteData<ChatroomsResponse>>(chatQueries.recentRoomsInfinite().queryKey, (old) =>
    upsertChatroomInfiniteData(old, normalizedInput),
  );
};
