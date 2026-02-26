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
  /** 메시지 ID — 채팅방 내 해당 질문 위치로 스크롤하기 위해 사용 */
  message_id?: number;
}
