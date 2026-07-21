import { parseSSEStream } from '@/features/chat/services/streamSseParser';
import type {
  ChatCancelGenerationResponseApi,
  ChatGenerationStatusResponseApi,
  SseStreamEventEnvelopeApi,
  StreamEvent,
} from '@/features/chat/types';
import { API } from '@/shared/api/endpoints';

export class ChatStreamHttpError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ChatStreamHttpError';
  }
}

/**
 * 실제 백엔드 API 연동 채팅 서비스
 *
 * SSE(Server-Sent Events) 기반 스트리밍 API 호출
 * - credentials: 'include'로 HttpOnly Cookie 전송 (JWT 인증)
 * - AbortSignal을 통한 요청 취소 지원
 */
const realChatService = {
  /**
   * 질문 스트림 시작
   *
   * POST /api/v1/chat/stream
   * - 새 질문에 대한 SSE 스트림 응답 수신
   * - 이벤트 타입: status, sources, token, result, error
   * - session_id는 선택 값이며, 없으면 서버가 새 세션을 생성
   */
  streamChat: async (
    query: string,
    sessionId: string | undefined,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
    toolFilters?: string[],
  ) => {
    const payload: { query: string; session_id?: string; tool_filters?: string[] } = { query };
    if (sessionId) {
      payload.session_id = sessionId;
    }
    if (toolFilters?.length) {
      payload.tool_filters = toolFilters;
    }

    const res = await fetch(API.chat.stream, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
      signal,
    });

    if (!res.ok) {
      throw new ChatStreamHttpError(`Stream error: ${res.status}`, res.status);
    }

    await parseSSEStream(res, ({ event }) => onEvent(event));
  },

  getGenerationStatus: async (sessionId: string): Promise<ChatGenerationStatusResponseApi> => {
    const res = await fetch(API.chat.status(sessionId), {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new ChatStreamHttpError(`Generation status error: ${res.status}`, res.status);
    }

    return res.json();
  },

  reconnectChatStream: async (
    sessionId: string,
    onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(API.chat.reconnectStream(sessionId), {
      method: 'GET',
      credentials: 'include',
      signal,
    });

    if (!res.ok) {
      throw new ChatStreamHttpError(`Reconnect stream error: ${res.status}`, res.status);
    }

    await parseSSEStream(res, onEnvelope);
  },

  cancelGeneration: async (sessionId: string): Promise<ChatCancelGenerationResponseApi> => {
    const res = await fetch(API.chat.cancel(sessionId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });

    if (!res.ok) {
      throw new ChatStreamHttpError(`Cancel generation error: ${res.status}`, res.status);
    }

    return res.json();
  },

  /**
   * 마지막 턴 soft-delete
   *
   * POST /api/v1/chat/{session_id}/reset-last
   * - 질문 수정 시 기존 마지막 턴을 삭제한 후 재질문
   * - 실패해도 사용자 흐름을 block하지 않음
   */
  resetLastTurn: async (sessionId: string): Promise<{ status: string }> => {
    const res = await fetch(API.chat.resetLast(sessionId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });

    if (!res.ok) {
      console.warn(`[resetLastTurn] HTTP ${res.status} for session ${sessionId}`);
      return { status: 'error' };
    }

    return res.json();
  },
};

export default realChatService;
