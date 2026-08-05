import type { SyncRecordRetryResponse } from '../types/syncModel';

export interface RetryOutcome {
  kind: 'success' | 'partial' | 'failed';
  succeededCount: number;
  failedCount: number;
}

/**
 * 재시도 응답 요약 — 재시도는 HTTP 200이어도 부분/전면 실패가 정상 응답이다.
 * 백엔드는 `failed_ids`나 `remaining_missing_ids`가 하나라도 있으면
 * 이벤트를 failed로 되돌리므로, 성공 판정은 응답 본문으로만 할 수 있다.
 */
export const summarizeRetryOutcome = (response: SyncRecordRetryResponse): RetryOutcome => {
  let succeededCount = 0;
  let failedCount = 0;

  for (const record of response.records) {
    succeededCount += record.succeeded_count;
    // 재시도 실패분과 여전히 누락된 분은 겹칠 수 있어 합집합으로 센다.
    failedCount += new Set([...record.failed_ids, ...record.remaining_missing_ids]).size;
  }

  if (failedCount === 0) return { kind: 'success', succeededCount, failedCount };
  if (succeededCount > 0) return { kind: 'partial', succeededCount, failedCount };
  return { kind: 'failed', succeededCount, failedCount };
};
