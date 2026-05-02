import { isAxiosError } from 'axios';

/** 백엔드 정형 에러 응답의 `detail.code` enum (backend exception 문자열과 동기화 유지). */
export const API_ERROR_CODE = {
  INVALID_CREDENTIALS: 'invalid_credentials',
} as const;

export type ApiErrorCode = (typeof API_ERROR_CODE)[keyof typeof API_ERROR_CODE];

/** UserError 계열 응답 (`error_handlers/user.py`). 신규 도메인은 `parseApiError` 사용 권장. */
export interface ApiErrorBody {
  code: string;
  message: string;
  detail: Record<string, unknown>;
}

export interface ParsedApiError {
  code: string;
  message: string;
}

const FALLBACK_MESSAGE = '알 수 없는 오류가 발생했습니다.';

export function parseApiError(error: unknown): ParsedApiError {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const record = detail as Record<string, unknown>;
      const code = typeof record.code === 'string' ? record.code : 'unknown';
      const message = typeof record.message === 'string' ? record.message : FALLBACK_MESSAGE;
      return { code, message };
    }
    if (typeof detail === 'string') {
      return { code: 'unknown', message: detail };
    }
  }
  if (error instanceof Error && error.message) {
    return { code: 'unknown', message: error.message };
  }
  return { code: 'unknown', message: FALLBACK_MESSAGE };
}
