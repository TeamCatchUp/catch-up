import delay from '@/shared/mocks/delay';

import { buildStreamingMockAnswer, MOCK_SOURCES, MOCK_STREAM_STATUS_STEPS } from './data';
import type { MockStreamEvent } from './types';

/**
 * 목 스트림 시뮬레이션 설정값
 */
const TOKEN_CHUNK_SIZE = 3;
const STATUS_DELAY_MS = 500;
const SOURCE_DELAY_MS = 180;
const TOKEN_DELAY_MS = 28;
const DUPLICATE_REQUEST_WINDOW_MS = 1500;

const addDaysToIsoString = (isoString: string, days: number) => {
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return isoString;
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString();
};

interface SessionTurnState {
  turn: number;
  lastRequestSignature: string;
  lastRequestedAt: number;
}

const sessionTurnState = new Map<string, SessionTurnState>();

const toTokenChunks = (text: string, chunkSize = TOKEN_CHUNK_SIZE): string[] => {
  const chunks: string[] = [];
  let cursor = 0;
  while (cursor < text.length) {
    const nextCursor = Math.min(cursor + chunkSize, text.length);
    chunks.push(text.slice(cursor, nextCursor));
    cursor = nextCursor;
  }
  return chunks;
};

const toCandidateSources = (sources: typeof MOCK_SOURCES) =>
  sources.map((source) => ({ ...source, is_cited: false }));

const getTurnForRequest = (session_id: string, requestSignature: string) => {
  const now = Date.now();
  const prev = sessionTurnState.get(session_id);

  if (
    prev &&
    prev.lastRequestSignature === requestSignature &&
    now - prev.lastRequestedAt <= DUPLICATE_REQUEST_WINDOW_MS
  ) {
    return prev.turn;
  }

  const turn = (prev?.turn ?? 0) + 1;
  sessionTurnState.set(session_id, {
    turn,
    lastRequestSignature: requestSignature,
    lastRequestedAt: now,
  });
  return turn;
};

const buildStreamRequestSignature = (query: string) => `chat:${query.trim()}`;

const buildSourcesForTurn = (turn: number): typeof MOCK_SOURCES => {
  if (turn <= 1) {
    return MOCK_SOURCES.map((source) => ({ ...source }));
  }

  return MOCK_SOURCES.map((source, index) => {
    const isCitedInTurn2 = index === 1 || index === 3 || index === 4;
    const createdAt =
      typeof source.created_at === 'string' ? addDaysToIsoString(source.created_at, turn - 1) : source.created_at;

    return {
      ...source,
      index: index + 1,
      is_cited: isCitedInTurn2,
      title: source.title ? `${source.title} (답변 ${turn})` : source.title,
      text: source.text ? `${source.text} [답변 ${turn} 기준 재평가]` : source.text,
      created_at: createdAt,
    };
  });
};

const buildTurnTwoAnswer = (query: string) =>
  [
    `# "${query}"에 대한 보완 답변 (답변 2) [2]`,
    '',
    '첫 번째 답변 이후, 문서를 재선별해서 근거 구성을 다시 정리했습니다 [2].',
    '',
    '## 무엇이 바뀌었나',
    '- cited 기준을 정책/상태 문서 중심으로 재설정했습니다 [2].',
    '- 프론트 token 누적 렌더링 기준을 코드 근거로 다시 검증했습니다 [4].',
    '- resume API 진행 상태를 포함해 후속 동작을 정리했습니다 [5].',
    '',
    '## 처리 순서 [2][4]',
    '1. status: 현재 단계 표시',
    '2. sources: 후보/최종 출처 갱신',
    '3. token: 본문 실시간 누적 렌더링',
    '',
    '## 구현 포인트 [4][5]',
    '> 답변2에서는 cited source를 [2], [4], [5] 기준으로 표시합니다.',
    '',
    '```ts',
    'const citedOrder = [2, 4, 5] as const;',
    'const isCited = (index: number) => citedOrder.includes(index as 2 | 4 | 5);',
    '```',
    '',
    '따라서 오른쪽 사이드바의 cited 영역도 [2], [4], [5] 순서로 확인되어야 합니다 [2][4][5].',
  ].join('\n');

const buildAnswerByTurn = (query: string, turn: number) => {
  if (turn <= 1) return buildStreamingMockAnswer(query);
  return buildTurnTwoAnswer(query);
};

const throwIfAborted = (signal?: AbortSignal) => {
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError');
  }
};

const emitBackendLikeStream = async (
  query: string,
  session_id: string,
  turn: number,
  onEvent: (event: MockStreamEvent) => void,
  signal?: AbortSignal,
) => {
  const turnSources = buildSourcesForTurn(turn);

  for (const step of MOCK_STREAM_STATUS_STEPS) {
    throwIfAborted(signal);
    onEvent({ type: 'status', session_id, node: step.node, message: step.message });
    await delay(STATUS_DELAY_MS);
  }

  throwIfAborted(signal);
  onEvent({ type: 'sources', session_id, sources: toCandidateSources(turnSources) });
  await delay(SOURCE_DELAY_MS);

  const answer = buildAnswerByTurn(query, turn);
  const chunks = toTokenChunks(answer);
  for (const chunk of chunks) {
    throwIfAborted(signal);
    onEvent({ type: 'token', session_id, token: chunk });
    await delay(TOKEN_DELAY_MS);
  }

  throwIfAborted(signal);
  onEvent({ type: 'sources', session_id, sources: turnSources });

  throwIfAborted(signal);
  onEvent({
    type: 'result',
    session_id,
    answer,
    sources: turnSources,
    related_jira_issues: [],
    chat_history_id: `mock-history-${Date.now()}`,
    has_feedback: false,
  });
};

/**
 * 목 채팅 서비스
 * realChatService와 동일한 인터페이스를 제공하여 USE_MOCK 플래그로 전환 가능
 */
const mockChatService = {
  streamChat: async (
    query: string,
    session_id: string,
    onEvent: (event: MockStreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    const turn = getTurnForRequest(session_id, buildStreamRequestSignature(query));
    await emitBackendLikeStream(query, session_id, turn, onEvent, signal);
  },

  resetLastTurn: async (_session_id: string): Promise<{ status: string }> => {
    return { status: 'success' };
  },
};

export default mockChatService;
