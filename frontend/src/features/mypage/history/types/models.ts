/** 히스토리 정렬 기준 */
export type HistorySort = 'latest' | 'oldest';

/** 히스토리 기간 필터 값 (전체 포함) */
export type HistoryPeriod = 'all' | 'today' | 'sevenDays' | 'older';

/** 히스토리 그룹 키 (`'all'` 제외한 실제 섹션 단위) */
export type HistoryGroup = Exclude<HistoryPeriod, 'all'>;

/**
 * 드롭다운 필터에서 사용하는 옵션 항목
 * @typeParam T - 옵션 값의 문자열 리터럴 유니온 타입
 */
export interface HistoryFilterOption<T extends string> {
  /** 옵션 식별 값 */
  value: T;
  /** 사용자에게 표시되는 라벨 */
  label: string;
}

/** API 응답을 가공한 히스토리 아이템 */
export interface HistoryItem {
  /** 고유 식별자 (`id-sessionId-createdAt` 조합) */
  id: string;
  /** 채팅 세션 ID */
  sessionId: string;
  /** 사용자가 입력한 질문 내용 */
  query: string;
  /** 원본 생성일시 문자열 (ISO 8601) */
  createdAt: string;
  /** 파싱된 Date 객체 (정렬·그루핑에 사용) */
  rawDate: Date;
  /** 포맷된 전체 날짜 문자열 (예: `2026.02.17`) */
  fullDate: string;
  /** 상대 시간 문자열 (예: `3일 전`) */
  relativeDate: string;
  /** 저장(북마크) 여부 */
  isSaved: boolean;
}
