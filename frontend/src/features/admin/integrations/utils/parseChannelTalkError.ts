import { isAxiosError } from 'axios';

/**
 * 백엔드 채널톡/Sync API 에러 응답 파서.
 *
 * 백엔드 형식 (FastAPI HTTPException으로 wrap된 형태):
 * ```
 * { detail: { code: string, message: string, metadata?, connector?, scope_id? } }
 * ```
 * shared/api/errors.ts의 `ApiErrorBody`(`{ code, message, detail }`)와는 구조가 다르므로
 * 이 파서로 일관된 `{ code, message }` 형태로 추출.
 */
export interface ParsedChannelTalkError {
  code: string;
  message: string;
}

const FALLBACK_MESSAGE = '알 수 없는 오류가 발생했습니다.';

export function parseChannelTalkError(error: unknown): ParsedChannelTalkError {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const record = detail as Record<string, unknown>;
      const code = typeof record.code === 'string' ? record.code : 'unknown';
      const message = typeof record.message === 'string' ? record.message : FALLBACK_MESSAGE;
      return { code, message };
    }
    // FastAPI 422 등은 detail이 string이거나 array일 수 있음
    if (typeof detail === 'string') {
      return { code: 'unknown', message: detail };
    }
  }
  if (error instanceof Error && error.message) {
    return { code: 'unknown', message: error.message };
  }
  return { code: 'unknown', message: FALLBACK_MESSAGE };
}
