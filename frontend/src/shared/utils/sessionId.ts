const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Mock 데이터는 UUID 형식이 아닌 session_id를 사용할 수 있어 개발 모드에서만 예외 허용
const ALLOW_NON_UUID_SESSION_ID = process.env.NEXT_PUBLIC_USE_MOCK === 'true';

export const isValidSessionId = (value: string | null | undefined): value is string => {
  // /chat/new 는 세션 미확정 placeholder 이므로 session API 호출 대상이 아님
  if (!value || value === 'new') return false;
  if (ALLOW_NON_UUID_SESSION_ID) return true;
  return UUID_REGEX.test(value);
};
