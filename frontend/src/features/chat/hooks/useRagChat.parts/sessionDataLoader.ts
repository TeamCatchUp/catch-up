import type { QueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

import type { ChatData, Message, SourceResponse } from '@/features/chat/types';
import { normalizeHistorySources } from '@/features/chat/utils/normalize/normalizeRagSources';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { ChatHistoryMessageResponse } from '@/shared/types/query/api';

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
      id: `history_${item.id}`,
      role: 'user',
      content: item.content ?? '',
      timestamp,
    };
  }

  const rawSources = Array.isArray(item.sources) ? (item.sources as SourceResponse[]) : [];

  return {
    id: `history_${item.id}`,
    role: 'assistant',
    content: item.content ?? '',
    sources: normalizeHistorySources(rawSources),
    detailed_tasks: [],
    timestamp,
    chat_history_id: item.chat_history_id ? String(item.chat_history_id) : String(item.id),
    has_feedback: Boolean(item.has_feedback),
  };
};

/**
 * "메시지 없는 빈 세션"을 프론트 표준 ChatData 형태로 생성
 * - 신규 UUID 세션 첫 진입, hydrate 실패 fallback 등에 사용
 */
export const createEmptyChatData = (
  sessionId: string,
  repo: string | null,
  initialQuery: string | null,
): ChatData => ({
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
    // React Query 캐시를 활용하면서 강제 fetch 동기화를 수행
    const response = await queryClient.fetchQuery(chatQueries.sessionMessages(sessionId, page, MESSAGE_PAGE_SIZE));

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

/**
 * 신규 세션에서 room 생성 전 messages 조회 시 발생할 수 있는 정상 404 판별 헬퍼
 */
export const isSessionMessagesNotFoundError = (err: unknown) =>
  isAxiosError(err) && err.response?.status === 404;
