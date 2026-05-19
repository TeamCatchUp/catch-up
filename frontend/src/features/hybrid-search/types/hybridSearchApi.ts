// hybrid-search API 타입 — backend snake_case 매칭.
// 백엔드: GET /api/v1/search/hybrid?keyword=&tool_filters=
// limit/offset은 backend가 제거 (d4f99ba7, PR #688) — dedup 후 최대 50개 전체 반환.

import type { SourceResponseApi } from '@/shared/types/sourceApi';

export type ToolFilter = 'jira' | 'github' | 'slack' | 'confluence' | 'channel_talk';

/** AccentTabs drill-down 탭 — 'all' 또는 단일 ToolFilter. */
export type ActiveTab = 'all' | ToolFilter;

export interface HybridSearchRequest {
  keyword: string;
  tool_filters?: ToolFilter[];
  /** UTC ISO datetime. created_at 필터 시작 */
  start_date?: string;
  /** UTC ISO datetime. created_at 필터 종료 */
  end_date?: string;
}

export interface HybridSearchResponse {
  results: SourceResponseApi[];
  total: number; // backend dedup 후 max 50
  source_distribution: Record<string, number>; // backend 계산값 (참고용, frontend는 results에서 자체 계산)
}

// URL ?tools= 파싱 시 화이트리스트 검증용.
export const TOOL_FILTERS: readonly ToolFilter[] = [
  'jira',
  'github',
  'slack',
  'confluence',
  'channel_talk',
] as const;

// scope fallback용 mutable 배열 (tools 없는 진입 시 5종 전체).
export const TOOL_FILTERS_ARRAY: ToolFilter[] = [...TOOL_FILTERS];
