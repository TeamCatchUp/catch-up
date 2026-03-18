/** 백엔드 구조화된 에러 응답 (error_handlers.py UserError 계열) */
export interface ApiErrorBody {
  code: string;
  message: string;
  detail: Record<string, unknown>;
}
