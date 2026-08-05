import type { AdminConnectorTargetRangeResponse } from '../types/syncModel';

/**
 * 한 번이라도 임베딩이 끝난(success/failed) target인가.
 *
 * `/admin/connector/status`의 targets는 "임베딩된 대상"이 아니라 "연결됨 ∪ 이력 있음"이다 —
 * 백엔드는 연결만 되고 sync 이력이 없는 target도 `sync_status: "pending"`, `event_id: ""`로
 * 합성해 내려준다. "임베딩된 X" 표와 히스토리는 이 필터를 거친 것만 보여야 한다.
 *
 * allowlist인 이유: 백엔드 스키마가 자유 문자열이라 상태값이 추가될 수 있는데,
 * blocklist면 미지의 상태가 "성공" 뱃지로 새어 나간다.
 */
export const isCompletedSyncTarget = (target: AdminConnectorTargetRangeResponse): boolean =>
  target.sync_status === 'success' || target.sync_status === 'failed';
