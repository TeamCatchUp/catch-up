import { isAxiosError } from 'axios';

/**
 * UserError 계열 백엔드 응답 — `error_handlers/user.py`에서 사용.
 * 응답 body 자체가 `{ code, message, detail }` 구조라 다른 정형 에러와 다름.
 *
 * 사용처: `app/(app)/admin/permissions/page.tsx`의 promote/revoke mutation 에러.
 * 현재 이 형식을 사용하는 다른 도메인은 없으며, 신규 도메인은 `parseApiError`를 사용 권장.
 */
export interface ApiErrorBody {
  code: string;
  message: string;
  detail: Record<string, unknown>;
}

/**
 * 백엔드 정형 에러 응답을 `{ code, message }` 객체로 정규화.
 *
 * 백엔드 표준 형식 (FastAPI HTTPException + `_build_error_detail` 패턴):
 * ```
 * { detail: { code: string, message: string, metadata?: object, ...추가필드 } }
 * ```
 * - `backend/catchup/server/sync/api.py` (sync API 전반)
 * - `backend/catchup/server/error_handlers/channel_talk.py` (채널톡 connector)
 * - 향후 추가될 모든 정형 에러 응답
 *
 * 폴백:
 * - `detail`이 string이면 FastAPI 기본 HTTPException → message로 사용 (code: "unknown")
 * - axios 자체 에러 (network/timeout 등) → error.message 사용
 * - 그 외 → 한국어 fallback message
 *
 * 사용 예:
 * ```ts
 * mutation.mutate(body, {
 *   onError: (error) => {
 *     const { code, message } = parseApiError(error);
 *     if (code === 'invalid_credentials') toast(...);
 *     else toast.error('실패했어요.', { description: message });
 *   },
 * });
 * ```
 */
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
