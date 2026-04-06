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
