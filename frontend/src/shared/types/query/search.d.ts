/** Popover 타입 */
export type PopoverType = 'person' | 'department' | 'project' | null;

/** 필터 레이블 */
export interface FilterLabels {
  person: string;
  dept: string;
  project: string;
}

/** 검색 쿼리 (최근 검색 기록) */
export interface SearchQuery {
  query: string;
  session_id: string;
  date: string;
  rawDate?: Date;
}
