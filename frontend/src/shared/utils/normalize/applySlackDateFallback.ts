import type { SourceResponseApi } from '@/shared/types/sourceApi';

// Slack은 백엔드 ingestion 단에서 편집된 메시지만 updated_at을 채움 (대부분 null).
// 시간 정렬·표시가 의미를 가지도록 created_at으로 폴백 — Slack 한정.
// 다른 소스는 ingestion 단에서 updated_at이 안정적으로 들어오므로 건드리지 않음.
// 정렬·정규화 직전에 한 번 적용.
export function applySlackDateFallback(
  items: readonly SourceResponseApi[],
): SourceResponseApi[] {
  return items.map((item) =>
    item.source === 'slack' && !item.updated_at && item.created_at
      ? { ...item, updated_at: item.created_at }
      : item,
  );
}
