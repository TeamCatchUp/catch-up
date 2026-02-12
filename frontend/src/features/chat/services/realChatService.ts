import { API } from '@/shared/api/endpoints';

/** SSE 스트림 라인 파싱 공통 로직 */
async function parseSSEStream(
  res: Response,
  onEvent: (event: StreamEvent) => void,
) {
  if (!res.ok) throw new Error(`Stream error: ${res.status}`);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6)) as StreamEvent;
          onEvent(event);
        } catch {
          // JSON 파싱 실패 무시
        }
      }
    }
  }
}

const realChatService = {
  /**
   * POST /api/chat/stream
   * 요청 자체가 SSE 스트림 응답을 반환
   */
  streamChat: async (
    query: string,
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
  ) => {
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
   * POST /api/chat/stream/resume
   * PR 선택 후 스트림 재개
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
