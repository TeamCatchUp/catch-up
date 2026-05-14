// hybrid-search API 타입 — backend snake_case 매칭.
// 백엔드: GET /api/v1/search/hybrid?keyword=&limit=&offset=&tool_filters=

import type { SourceResponseApi } from '@/shared/types/sourceApi';

export type ToolFilter = 'jira' | 'github' | 'slack' | 'confluence' | 'channel_talk';

export interface HybridSearchRequest {
  keyword: string;
  limit?: number;
  offset?: number;
  tool_filters?: ToolFilter[];
}

export interface HybridSearchResponse {
  results: SourceResponseApi[];
  total: number; // backend cap 200
  source_distribution: Record<string, number>;
}

// URL ?tools= 파싱 시 화이트리스트 검증용.
export const TOOL_FILTERS: readonly ToolFilter[] = [
  'jira',
  'github',
  'slack',
  'confluence',
  'channel_talk',
] as const;
