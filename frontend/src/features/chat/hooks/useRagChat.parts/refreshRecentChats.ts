import type { QueryClient } from '@tanstack/react-query';

import { chatQueries } from '@/shared/queries/chatroom.queries';

/**
 * 최근 채팅/질문 목록을 갱신
 * - 사이드바 리프레시 커스텀 이벤트 발생
 * - TanStack Query 캐시 무효화
 */
export const refreshRecentChats = (queryClient: QueryClient) => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('refresh_sidebar'));
  }
  void queryClient.invalidateQueries({ queryKey: chatQueries.lists() });
};
