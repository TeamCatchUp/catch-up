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
   * POST /api/chat/stream
   * - 새 질문에 대한 SSE 스트림 응답 수신
   * - 이벤트 타입: status, sources, token/delta, interrupt, result, error
   *
   * @param query - 질문 내용
   * @param sessionId - 현재 세션 ID
   * @param onEvent - 스트림 이벤트를 처리할 콜백
   * @param signal - 요청 취소용 AbortSignal (옵셔널)
   * @throws HTTP 에러 또는 네트워크 에러
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
   * PR 선택 후 스트림 재개
   *
   * POST /api/chat/stream/resume
   * - interrupt 이벤트 이후 사용자가 선택한 PR 정보 전송
   * - 백엔드에서 선택된 PR을 기반으로 답변 생성 재개
   *
   * @param sessionId - 현재 세션 ID
   * @param selectedPRs - 사용자가 선택한 PR 목록
   * @param onEvent - 스트림 이벤트를 처리할 콜백
   * @param signal - 요청 취소용 AbortSignal (옵셔널)
   * @throws HTTP 에러 또는 네트워크 에러
   */
  resumeStream: async (
    sessionId: string,
    selectedPRs: { pr_number: number; repo_name: string; owner: string }[],
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    const res = await fetch(API.chat.streamResume, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        session_id: sessionId,
        user_selected_pull_requests: selectedPRs.map((pr) => ({
          pr_number: pr.pr_number,
          repo_name: pr.repo_name,
          owner: pr.owner,
        })),
      }),
      signal,
    });

    await parseSSEStream(res, onEvent);
  },
};

export default realChatService;
