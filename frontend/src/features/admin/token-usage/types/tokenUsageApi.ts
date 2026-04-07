/** 백엔드 GET /api/v1/stats/costs/tokens/me, /org 응답 */

/** 일자별 토큰 사용 엔트리 */
export interface ChatTokenUsageDateEntry {
  from_date: string;
  to_date: string;
  input_tokens: number;
  output_tokens: number;
  usd: number;
}

/** 토큰 사용량 응답 */
export interface ChatTokenUsageResponse {
  total_usd: number;
  daily_avg_usd: number;
  by_date: ChatTokenUsageDateEntry[];
  start_date: string | null;
  end_date: string | null;
}

/** 토큰 사용량 요청 파라미터 */
export interface ChatTokenUsageParams {
  start_date: string;
  end_date?: string;
}

/** ── 질문 횟수 ── */

/** 일자별 질문 횟수 엔트리 */
export interface QuestionCountDateEntry {
  from_date: string;
  to_date: string;
  question_count: number;
}

/** 질문 횟수 응답 */
export interface QuestionCountResponse {
  total_count: number;
  daily_avg_count: number;
  by_date: QuestionCountDateEntry[];
  start_date: string | null;
  end_date: string | null;
}

/** ── 랭킹 ── */

/** 랭킹 엔트리 */
export interface UserTokenCostRankingItem {
  user_id: number;
  user_name: string;
  department: string;
  total_usd: number;
}

/** 랭킹 응답 */
export interface UserTokenCostRankingResponse {
  ranking: UserTokenCostRankingItem[];
  start_date: string | null;
  end_date: string | null;
}
