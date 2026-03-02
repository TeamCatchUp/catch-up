const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const isValidSessionId = (value: string | null | undefined): value is string => {
  // /chat/new 는 세션 미확정 placeholder 이므로 session API 호출 대상이 아님
  if (!value || value === 'new') return false;
  return UUID_REGEX.test(value);
};
