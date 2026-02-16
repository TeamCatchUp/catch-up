import type { StreamEvent } from '@/features/chat/types';
import { API } from '@/shared/api/endpoints';

/**
 * SSE 스트림 파싱 공통 로직
 *
 * ReadableStream을 읽어 SSE 형식의 이벤트를 파싱
 * - SSE 형식: "data: {json}\n\n" 블록 단위로 이벤트 전송
 * - 블록은 "\n\n"으로 구분
 * - 각 블록 내에서 "data:" 접두사를 가진 라인들을 추출하여 JSON 파싱
 * - 파싱 실패 시 무시 (malformed payload)
 *
 * @param res - fetch 응답 객체 (Response.body 필수)
 * @param onEvent - 파싱된 이벤트를 처리할 콜백
 * @throws HTTP 에러 또는 빈 응답 body
 */
async function parseSSEStream(res: Response, onEvent: (event: StreamEvent) => void) {
  if (!res.ok) throw new Error(`Stream error: ${res.status}`);

  if (!res.body) {
    throw new Error('Stream error: empty response body');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  /**
   * SSE 블록 파싱
   * "data:" 접두사를 가진 라인들을 추출하여 JSON으로 파싱
   */
  const parseBlock = (block: string) => {
    const dataLines = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart());

    if (dataLines.length === 0) return;

    const raw = dataLines.join('\n');

    try {
      const event = JSON.parse(raw) as StreamEvent;
      onEvent(event);
    } catch {
      // 잘못된 형식의 payload는 무시
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';

    for (const block of blocks) {
      parseBlock(block);
    }

    if (done) break;
  }

  const tail = buffer.trim();
  if (tail) {
    parseBlock(tail);
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
   * - 이벤트 타입: status, sources, token/delta, interrupt, result, error
   */
  streamChat: async (query: string, sessionId: string, onEvent: (event: StreamEvent) => void, signal?: AbortSignal) => {
    const res = await fetch(API.chat.stream, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ query, session_id: sessionId }),
      signal,
    });

    await parseSSEStream(res, onEvent);
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

  // TODO: resume API 백엔드 구현 시 재활성
  // resumeStream: async (
  //   sessionId: string,
  //   selectedPRs: { pr_number: number; repo_name: string; owner: string }[],
  //   onEvent: (event: StreamEvent) => void,
  //   signal?: AbortSignal,
  // ) => { ... },
};

export default realChatService;
