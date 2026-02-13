/**
 * pending 초기 질문 키 생성
 * sessionStorage에 임시 저장된 질문을 가져올 때 사용
 *
 * @param sessionId - 세션 ID
 * @returns sessionStorage 키
 */
export const getPendingInitialQueryKey = (sessionId: string) => `pending_chat_query_${sessionId}`;

/**
 * 실제로 사용할 초기 질문 결정
 *
 * 우선순위:
 * 1. props로 전달받은 initialQuery
 * 2. URL 쿼리 파라미터 'q'
 * 3. sessionStorage에 저장된 pending 질문
 *
 * @param initialQuery - props로 전달받은 초기 질문
 * @param sessionId - 세션 ID
 * @returns 실제 사용할 초기 질문 또는 null
 */
export const getEffectiveInitialQuery = (initialQuery: string | null, sessionId: string): string | null => {
  const trimmed = initialQuery?.trim();
  if (trimmed) return trimmed;

  if (typeof window === 'undefined') return null;
  const fromUrl = new URLSearchParams(window.location.search).get('q')?.trim();
  if (fromUrl) return fromUrl;

  const fromPending = sessionStorage.getItem(getPendingInitialQueryKey(sessionId))?.trim();
  return fromPending || null;
};

/**
 * sessionStorage에 저장된 pending 초기 질문 제거
 * 스트림 시작 후 호출하여 중복 실행 방지
 *
 * @param sessionId - 세션 ID
 */
export const clearPendingInitialQuery = (sessionId: string) => {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(getPendingInitialQueryKey(sessionId));
};
