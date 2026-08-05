import { describe, expect, it } from 'vitest';

import type { SyncRecordRetryResponse } from '../types/syncModel';
import { summarizeRetryOutcome } from './retryOutcome';

const baseResponse = (records: SyncRecordRetryResponse['records']): SyncRecordRetryResponse => ({
  connector: 'github',
  scope_id: 'org',
  target_id: 'repo',
  target_name: 'repo',
  event_id: 'evt-1',
  event_status: null,
  records,
});

const record = (over: Partial<SyncRecordRetryResponse['records'][number]>) => ({
  record_type: 'issue',
  requested_ids: [] as string[],
  retried_count: 0,
  succeeded_count: 0,
  failed_ids: [] as string[],
  remaining_missing_ids: [] as string[],
  ...over,
});

describe('summarizeRetryOutcome', () => {
  it('실패가 하나도 없으면 success', () => {
    const outcome = summarizeRetryOutcome(
      baseResponse([record({ retried_count: 3, succeeded_count: 3 })]),
    );
    expect(outcome).toEqual({ kind: 'success', succeededCount: 3, failedCount: 0 });
  });

  it('성공과 실패가 섞이면 partial', () => {
    const outcome = summarizeRetryOutcome(
      baseResponse([
        record({ succeeded_count: 2, failed_ids: ['a'] }),
        record({ succeeded_count: 1, remaining_missing_ids: ['b', 'c'] }),
      ]),
    );
    expect(outcome).toEqual({ kind: 'partial', succeededCount: 3, failedCount: 3 });
  });

  it('전면 실패면 failed — HTTP 200이어도 성공이 아니다', () => {
    const outcome = summarizeRetryOutcome(
      baseResponse([record({ retried_count: 2, failed_ids: ['a', 'b'] })]),
    );
    expect(outcome).toEqual({ kind: 'failed', succeededCount: 0, failedCount: 2 });
  });

  it('failed_ids와 remaining_missing_ids가 겹치면 한 번만 센다', () => {
    const outcome = summarizeRetryOutcome(
      baseResponse([record({ failed_ids: ['a', 'b'], remaining_missing_ids: ['b', 'c'] })]),
    );
    expect(outcome.failedCount).toBe(3);
  });

  it('records가 비어 있으면 success로 본다', () => {
    expect(summarizeRetryOutcome(baseResponse([])).kind).toBe('success');
  });
});
