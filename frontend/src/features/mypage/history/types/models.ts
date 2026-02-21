import type { FilterOption } from '@/shared/components/ui/filter-dropdown';
import type { DateGroup, DatePeriod, SortOrder } from '@/shared/utils/dateGrouping';

/** @deprecated shared FilterOption 사용 */
export type HistoryFilterOption<T extends string> = FilterOption<T>;

/** 히스토리 정렬 기준 */
export type HistorySort = SortOrder;

/** 히스토리 기간 필터 값 (전체 포함) */
export type HistoryPeriod = DatePeriod;

/** 히스토리 그룹 키 */
export type HistoryGroup = DateGroup;

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
