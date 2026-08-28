// 문서 탐색 submit용 /hybrid-search 쿼리 URL 조립.
// 키·직렬화는 useHybridSearchUrlState의 파싱 규약(q·tools·start·end·smart_filter)과 짝을 이룬다.

import type { DateRange } from 'react-day-picker';

import type { DocsSource } from '@/shared/types/source';

import { dateRangeToUrlParams } from './temporalRange';

export const HYBRID_SEARCH_PATHNAME = '/hybrid-search';

export interface BuildHybridSearchUrlInput {
  query: string;
  sources?: DocsSource[];
  dateRange?: DateRange;
  smartFilter: boolean;
}

// 공백뿐인 질의는 URL을 만들지 않는다 — 호출부가 submit을 중단하도록 null을 돌려준다.
export function buildHybridSearchUrl({
  query,
  sources,
  dateRange,
  smartFilter,
}: BuildHybridSearchUrlInput): string | null {
  const trimmed = query.trim();
  if (!trimmed) return null;

  const params = new URLSearchParams({ q: trimmed, smart_filter: String(smartFilter) });
  if (sources && sources.length > 0) {
    params.set('tools', sources.join(','));
  }
  const { start, end } = dateRangeToUrlParams(dateRange);
  if (start) params.set('start', start);
  if (end) params.set('end', end);

  return `${HYBRID_SEARCH_PATHNAME}?${params.toString()}`;
}
