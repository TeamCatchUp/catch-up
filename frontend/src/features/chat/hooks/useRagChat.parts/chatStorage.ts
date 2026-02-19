import type { ChatData } from '@/features/chat/types';
import { getFromLocalStorage, setToLocalStorage } from '@/shared/hooks/useLocalStorage';
import { MOCK_INITIAL_MESSAGES } from '@/shared/mocks/chat/data';
import { USE_MOCK } from '@/shared/mocks/config';

/**
 * localStorage에서 저장된 채팅 데이터를 불러옴
 *
 * 마지막 메시지가 user 메시지인 경우 빈 assistant 메시지를 추가하여 복구
 * (스트림 중단 또는 페이지 새로고침 시 발생 가능)
 *
 * @param key - localStorage 키 (세션별로 고유)
 * @returns 저장된 채팅 데이터 또는 null
 */
export const loadSavedChat = (key: string): ChatData | null => {
  const parsedData = getFromLocalStorage<ChatData | null>(key, null);
  if (!parsedData) return null;

  const lastMessage = parsedData.messages[parsedData.messages.length - 1];

  if (lastMessage?.role === 'user') {
    const repairedData: ChatData = {
      ...parsedData,
      messages: [
        ...parsedData.messages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          sources: [],
          detailed_tasks: [],
          timestamp: new Date().toISOString(),
        },
      ],
    };
    setToLocalStorage(key, repairedData);
    return repairedData;
  }

  return parsedData;
};

/**
 * 초기 채팅 데이터 생성
 *
 * 우선순위:
 * 1. localStorage에 저장된 데이터
 * 2. initialQuery가 있으면 user 메시지로 시작
 * 3. USE_MOCK이면 목 데이터 사용
 * 4. 빈 채팅 세션
 *
 * @param sessionId - 세션 ID
 * @param repo - 저장소 정보
 * @param initialQuery - 초기 질문
 * @param storageKey - localStorage 키
 * @returns 초기 채팅 데이터
 */
export const buildInitialChatData = (
  sessionId: string,
  repo: string | null,
  initialQuery: string | null,
  storageKey: string,
): ChatData => {
  const saved = loadSavedChat(storageKey);
  if (saved) return saved;

  if (initialQuery) {
    return {
      session_id: sessionId,
      title: initialQuery,
      repo: repo || '',
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: initialQuery,
          timestamp: new Date().toISOString(),
        },
      ],
    };
  }

  if (USE_MOCK) {
    return {
      session_id: sessionId,
      title: '로그인 인증 흐름을 설명해주세요',
      repo: repo || '',
      messages: MOCK_INITIAL_MESSAGES,
    };
  }

  return { session_id: sessionId, title: '', repo: repo || '', messages: [] };
};
