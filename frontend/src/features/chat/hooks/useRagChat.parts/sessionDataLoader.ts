import type { QueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

import type { ChatData, Message, SourceResponse } from '@/features/chat/types';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { ChatHistoryMessageResponse } from '@/shared/types/query/api';
import { normalizeHistorySources } from '@/shared/utils/normalize/normalizeRagSources';

// 한 페이지 기본 로딩 크기
export const MESSAGE_PAGE_SIZE = 50;

interface LoadSessionChatDataOptions {
  queryClient: QueryClient;
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
}

// created_at가 비정상 값이어도 정렬이 깨지지 않도록 number fallback 보정
const toComparableTimestamp = (iso: string) => {
  const parsed = new Date(iso).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
};

/**
 * API message 1건을 UI message 모델로 변환
 *
 * backend schema와 frontend schema의 차이:
 * - `sender_type: human|assistant` -> `role: user|assistant`
 * - assistant일 때만 sources/feedback 관련 필드를 채움
 */
export const toUiMessage = (item: ChatHistoryMessageResponse): Message => {
  const timestamp = item.created_at || new Date().toISOString();

  if (item.sender_type === 'human') {
    return {
      id: String(item.id),
      role: 'user',
      content: item.content ?? '',
      timestamp,
    };
  }

  const rawSources = Array.isArray(item.sources) ? (item.sources as SourceResponse[]) : [];

  return {
    id: String(item.id),
    role: 'assistant',
    content: item.content ?? '',
    sources: normalizeHistorySources(rawSources),
    timestamp,
    chat_history_id: item.chat_history_id ? String(item.chat_history_id) : String(item.id),
    has_feedback: Boolean(item.has_feedback),
    is_liked: item.is_liked === true ? true : item.is_liked === false ? false : undefined,
    is_saved: item.is_saved ?? undefined,
  };
};

/**
 * "메시지 없는 빈 세션"을 프론트 표준 ChatData 형태로 생성
 * - 신규 UUID 세션 첫 진입, hydrate 실패 fallback 등에 사용
 */
export const createEmptyChatData = (sessionId: string, repo: string | null, initialQuery: string | null): ChatData => ({
  session_id: sessionId,
  title: initialQuery ?? '',
  repo: repo ?? '',
  messages: [],
});

/**
 * 세션 메시지 API(page 기반)를 끝까지 순회해서 프론트 표준 ChatData 형태로 변환한다.
 * - `sender_type` -> `role`
 * - source payload 정규화
 * - created_at/id 기준 정렬 보정
 */
export const loadSessionChatData = async ({
  queryClient,
  sessionId,
  repo,
  initialQuery,
}: LoadSessionChatDataOptions): Promise<ChatData> => {
  // page API를 끝까지 순회하며 합친다.
  let page = 1;
  let title = '';
  let total = 0;
  const allItems: ChatHistoryMessageResponse[] = [];

  while (true) {
    // staleTime: 0으로 글로벌 staleTime(60s)을 무시하고 항상 최신 데이터를 유지
    // 스트림 종료 직후 서버 동기화에서 캐시된 이전 데이터를 반환하는 문제를 방지
    const response = await queryClient.fetchQuery({
      ...chatQueries.sessionMessages(sessionId, page, MESSAGE_PAGE_SIZE),
      staleTime: 0,
    });

    title = response.title || title;
    total = response.total;
    allItems.push(...response.items);

    // 총 개수 도달 또는 빈 페이지면 종료
    if (allItems.length >= total || response.items.length === 0) {
      break;
    }

    page += 1;
  }

  // API 응답 순서에 의존하지 않도록 timestamp/id 기준으로 재정렬
  const sortedMessages = [...allItems].sort((a, b) => {
    const byCreatedAt = toComparableTimestamp(a.created_at) - toComparableTimestamp(b.created_at);
    if (byCreatedAt !== 0) return byCreatedAt;
    return a.id - b.id;
  });

  return {
    session_id: sessionId,
    title: title || initialQuery || '',
    repo: repo ?? '',
    messages: sortedMessages.map(toUiMessage),
  };
};

// ---------------------------------------------------------------------------
// 역방향 무한 스크롤용 로더
// ---------------------------------------------------------------------------

export interface LatestPageResult {
  chatData: ChatData;
  /** 현재 로드된 가장 오래된 페이지 번호 */
  oldestLoadedPage: number;
  /** 총 페이지 수 */
  totalPages: number;
}

const sortItems = (items: ChatHistoryMessageResponse[]) =>
  [...items].sort((a, b) => {
    const byCreatedAt = toComparableTimestamp(a.created_at) - toComparableTimestamp(b.created_at);
    if (byCreatedAt !== 0) return byCreatedAt;
    return a.id - b.id;
  });

/**
 * 마지막 페이지(최신 메시지)만 로드하는 로더.
 * - page 1을 먼저 fetch해 total을 확인하고, 마지막 페이지를 계산해 로드
 * - 1페이지뿐이면 그대로 사용
 */
export const loadLatestSessionPage = async ({
  queryClient,
  sessionId,
  repo,
  initialQuery,
}: LoadSessionChatDataOptions): Promise<LatestPageResult> => {
  // page 1을 먼저 가져와서 total 확인
  const firstResponse = await queryClient.fetchQuery({
    ...chatQueries.sessionMessages(sessionId, 1, MESSAGE_PAGE_SIZE),
    staleTime: 0,
  });

  const total = firstResponse.total;
  const totalPages = Math.max(1, Math.ceil(total / MESSAGE_PAGE_SIZE));

  if (totalPages <= 1) {
    return {
      chatData: {
        session_id: sessionId,
        title: firstResponse.title || initialQuery || '',
        repo: repo ?? '',
        messages: sortItems(firstResponse.items).map(toUiMessage),
      },
      oldestLoadedPage: 1,
      totalPages: 1,
    };
  }

  // 마지막 페이지 로드
  const lastResponse = await queryClient.fetchQuery({
    ...chatQueries.sessionMessages(sessionId, totalPages, MESSAGE_PAGE_SIZE),
    staleTime: 0,
  });

  return {
    chatData: {
      session_id: sessionId,
      title: lastResponse.title || firstResponse.title || initialQuery || '',
      repo: repo ?? '',
      messages: sortItems(lastResponse.items).map(toUiMessage),
    },
    oldestLoadedPage: totalPages,
    totalPages,
  };
};

/**
 * 이전 페이지 1개를 로드하여 Message[] 배열로 반환한다.
 * 채팅 역방향 무한 스크롤에서 위로 스크롤 시 호출.
 */
export const loadPreviousSessionPage = async ({
  queryClient,
  sessionId,
  page,
}: {
  queryClient: QueryClient;
  sessionId: string;
  page: number;
}): Promise<Message[]> => {
  const response = await queryClient.fetchQuery({
    ...chatQueries.sessionMessages(sessionId, page, MESSAGE_PAGE_SIZE),
    staleTime: 0,
  });

  return sortItems(response.items).map(toUiMessage);
};

/**
 * 신규 세션에서 room 생성 전 messages 조회 시 발생할 수 있는 정상 404 판별 헬퍼
 */
export const isSessionMessagesNotFoundError = (err: unknown) => isAxiosError(err) && err.response?.status === 404;
