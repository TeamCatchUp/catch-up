/** 일자별 토큰 사용 데이터 (bar chart) */
export interface DailyTokenUsage {
  date: string;
  cost: number;
  model_name: string;
}

/** 전체 토큰 사용량 추이 (line chart) */
export interface TotalTokenUsageTrend {
  date: string;
  cumulative_tokens: number;
}

/** 전체 질문 횟수 (bar chart) */
export interface TotalQuestionCount {
  date: string;
  count: number;
}

/** 나의 토큰 사용 요약 */
export interface TokenUsageSummary {
  total_cost: number;
  status: 'normal' | 'warning' | 'exceeded';
}

/** 조직 멤버 정보 */
export interface OrgMember {
  id: string;
  name: string;
  team: string;
  position: string;
  role: string;
  profileImage?: string;
  tokenEnabled: boolean;
  cost: number;
}

/** 토큰 사용량 순위 항목 */
export interface TokenUsageRankingEntry {
  rank: number;
  member: OrgMember;
  cost: number;
}
