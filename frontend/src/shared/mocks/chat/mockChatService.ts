import delay from '@/shared/mocks/delay';

import { buildStreamingMockAnswer, MOCK_SOURCES, MOCK_STREAM_STATUS_STEPS } from './data';
import type { MockStreamEvent } from './types';

/**
 * 목 스트림 시뮬레이션 설정값
 */
const TOKEN_CHUNK_SIZE = 3; // 토큰을 몇 글자씩 나눌지
const STATUS_DELAY_MS = 500; // status 이벤트 간격
const SOURCE_DELAY_MS = 180; // sources 이벤트 지연
const TOKEN_DELAY_MS = 28; // token 이벤트 간격 (실시간 타이핑 효과)
const DUPLICATE_REQUEST_WINDOW_MS = 1500; // 중복 요청 감지 시간 윈도우

const addDaysToIsoString = (isoString: string, days: number) => {
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return isoString;
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString();
};

/**
 * 세션별 턴 상태 추적
 * - 같은 세션에서 여러 번 질문 시 턴 증가
 * - 중복 요청(1.5초 이내 동일 요청)은 턴 증가 안 함
 */
interface SessionTurnState {
  turn: number;
  lastRequestSignature: string;
  lastRequestedAt: number;
}

const sessionTurnState = new Map<string, SessionTurnState>();

/**
 * 텍스트를 토큰 단위로 분할
 * 실시간 스트리밍 효과를 위해 몇 글자씩 나눔
 */
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

/**
 * 후보 출처 생성 (is_cited를 모두 false로 설정)
 * 'sources' 이벤트의 첫 번째 전송 시 사용 (source_candidates 역할)
 */
const toCandidateSources = (sources: typeof MOCK_SOURCES) =>
  sources.map((source) => ({
    ...source,
    is_cited: false,
  }));

/**
 * 요청에 대한 턴 번호 계산
 * - 중복 요청(1.5초 이내 동일)은 같은 턴 유지
 * - 새 요청이면 턴 증가
 *
 * @param sessionId - 세션 ID
 * @param requestSignature - 요청 시그니처 (query 또는 PR 선택 조합)
 * @returns 현재 턴 번호
 */
const getTurnForRequest = (sessionId: string, requestSignature: string) => {
  const now = Date.now();
  const prev = sessionTurnState.get(sessionId);

  if (
    prev &&
    prev.lastRequestSignature === requestSignature &&
    now - prev.lastRequestedAt <= DUPLICATE_REQUEST_WINDOW_MS
  ) {
    return prev.turn;
  }

  const turn = (prev?.turn ?? 0) + 1;
  sessionTurnState.set(sessionId, {
    turn,
    lastRequestSignature: requestSignature,
    lastRequestedAt: now,
  });

  return turn;
};

/**
 * 질문 요청 시그니처 생성
 * @param query - 질문 내용
 * @returns 요청 시그니처 (chat:{query})
 */
const buildStreamRequestSignature = (query: string) => `chat:${query.trim()}`;

/**
 * 턴별로 다른 출처 데이터 생성
 * - turn 1: 원본 MOCK_SOURCES
 * - turn 2 이상: cited 인덱스 변경([2], [4], [5]), 제목/내용 수정, 시간 증가
 *
 * @param turn - 현재 턴 번호
 * @returns 턴에 맞는 출처 목록
 */
const buildSourcesForTurn = (turn: number): typeof MOCK_SOURCES => {
  if (turn <= 1) {
    return MOCK_SOURCES.map((source) => ({ ...source }));
  }

  return MOCK_SOURCES.map((source, index) => {
    // turn2 이후 cited 인덱스: [2], [4], [5]
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

/**
 * AbortSignal 체크
 * 사용자가 중단 요청한 경우 AbortError 발생
 */
const throwIfAborted = (signal?: AbortSignal) => {
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError');
  }
};

/**
 * 백엔드 스트림 시뮬레이션
 *
 * 실제 백엔드와 동일한 순서로 이벤트 전송:
 * 1. status 이벤트들 (router, rewrite, search 등)
 * 2. sources 이벤트 (후보 출처, is_cited=false)
 * 3. token 이벤트들 (답변 내용 스트리밍)
 * 4. sources 이벤트 (최종 cited 출처, is_cited=true)
 *
 * @param query - 질문 내용
 * @param sessionId - 세션 ID
 * @param turn - 현재 턴 번호
 * @param onEvent - 이벤트 핸들러
 * @param signal - 중단 시그널
 */
const emitBackendLikeStream = async (
  query: string,
  sessionId: string,
  turn: number,
  onEvent: (event: MockStreamEvent) => void,
  signal?: AbortSignal,
) => {
  const turnSources = buildSourcesForTurn(turn);

  for (const step of MOCK_STREAM_STATUS_STEPS) {
    throwIfAborted(signal);
    onEvent({
      type: 'status',
      session_id: sessionId,
      node: step.node,
      message: step.message,
    });
    await delay(STATUS_DELAY_MS);
  }

  throwIfAborted(signal);
  onEvent({
    type: 'sources',
    session_id: sessionId,
    sources: toCandidateSources(turnSources),
  });
  await delay(SOURCE_DELAY_MS);

  const answer = buildAnswerByTurn(query, turn);
  const chunks = toTokenChunks(answer);
  for (const chunk of chunks) {
    throwIfAborted(signal);
    onEvent({
      type: 'token',
      session_id: sessionId,
      token: chunk,
    });
    await delay(TOKEN_DELAY_MS);
  }

  throwIfAborted(signal);
  onEvent({
    type: 'sources',
    session_id: sessionId,
    sources: turnSources,
  });

  throwIfAborted(signal);
  onEvent({
    type: 'result',
    session_id: sessionId,
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
  /**
   * 질문 스트림 시작 (목 버전)
   * - 턴별로 다른 출처와 답변 제공
   * - 실제 백엔드와 동일한 이벤트 순서 시뮬레이션
   *
   * @param query - 질문 내용
   * @param sessionId - 세션 ID
   * @param onEvent - 이벤트 핸들러
   * @param signal - 중단 시그널
   */
  streamChat: async (
    query: string,
    sessionId: string,
    onEvent: (event: MockStreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    const turn = getTurnForRequest(sessionId, buildStreamRequestSignature(query));
    await emitBackendLikeStream(query, sessionId, turn, onEvent, signal);
  },

  /**
   * 마지막 턴 soft-delete (목 버전)
   * - 항상 성공 반환
   */
  resetLastTurn: async (_sessionId: string): Promise<{ status: string }> => {
    return { status: 'success' };
  },
};

export default mockChatService;
