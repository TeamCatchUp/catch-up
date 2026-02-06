/**
 * RAG 채팅 API 래퍼
 * chatService에 위임하는 편의 함수들
 */

import chatService from '@/services/chat/chatService';

/** SSE 연결 생성 */
export const createSSEConnection = (
  sessionId: string,
  onMessage: (notification: RagNotification) => void,
  onError?: (error: Event) => void,
  onOpen?: () => void,
): EventSource => chatService.createSSEConnection(sessionId, onMessage, onError, onOpen);

/** 채팅 요청 */
export const sendChatQuery = async (
  queryText: string,
  sessionId: string,
  indexList: string[],
): Promise<ChatResponse> => chatService.sendChatQuery(queryText, sessionId, indexList);

/** 답변 생성 재개 요청 */
export const resumeChatQuery = async (
  sessionId: string,
  userSelectedPullRequests: { prNumber: number; repoName: string; owner: string }[],
): Promise<ChatResponse> => chatService.resumeChatQuery(sessionId, userSelectedPullRequests);
