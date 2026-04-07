/** 일자별 토큰 사용 데이터 (bar chart) */
export interface DailyTokenUsage {
  date: string;
  cost: number;
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
  daily_avg_usd: number;
}

/** 조직 멤버 정보 */
export interface OrgMember {
  id: string;
  name: string;
  team: string;
  position: string;
  role: string;
  profileImage?: string;
}

/** 토큰 사용량 순위 항목 */
export interface TokenUsageRankingEntry {
  rank: number;
  user_id: number;
  user_name: string;
  department: string;
  total_usd: number;
}

/** 제한 해제 요청 */
export interface LimitReleaseRequest {
  id: string;
  userId: string;
  name: string;
  email: string;
  profileImage?: string;
  team: string;
  position: string;
  cost: number;
  requestedAmount: number;
  reason: string;
  dailyLimit: number;
  monthlyLimit: number;
  requestedAt: string;
}

/** 제한 해제 요청 테이블 행 */
export interface LimitReleaseTableRow {
  key: string;
  name: string;
  profileImage?: string;
  cost: number;
  requestedAmount: number;
  position: string;
  team: string;
}
