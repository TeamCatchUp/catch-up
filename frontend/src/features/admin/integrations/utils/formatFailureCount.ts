/** 실패 건수 표시 상한. Figma 17169:73960 — 초과하면 "50,000+건"으로 고정한다 */
const FAILURE_COUNT_CAP = 50_000;

/**
 * 임베딩 실패 건수를 배지 문구로 만든다.
 *
 * 상한을 넘으면 "+"로 접는다. 정확히 상한이면 붙이지 않는다(사용자 결정).
 * 이 규칙은 실패 건수에만 쓴다 — 채널톡 하단바 집계나 필터 건수 배지에는 적용하지 않는다.
 */
export const formatFailureCount = (count: number): string => {
  const safe = Math.max(0, Math.floor(count));
  if (safe > FAILURE_COUNT_CAP) return `${FAILURE_COUNT_CAP.toLocaleString('ko-KR')}+건`;
  return `${safe.toLocaleString('ko-KR')}건`;
};
