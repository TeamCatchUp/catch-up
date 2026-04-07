/** API 응답에서 연동 여부 값을 최대한 안전하게 해석 */
export const parseConnected = (value: unknown, fallback = false): boolean => {
  if (typeof value === 'boolean') return value;
  if (Array.isArray(value)) return value.length > 0;

  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const candidate = obj.connected ?? obj.is_connected ?? obj.installed ?? obj.enabled ?? obj.active;
    if (typeof candidate === 'boolean') return candidate;
  }

  return fallback;
};

/** API 응답 객체에서 문자열 필드를 우선순위에 따라 탐색 */
export const pickString = (value: unknown, keys: string[], fallback: string): string => {
  if (!value || typeof value !== 'object') return fallback;
  const obj = value as Record<string, unknown>;

  for (const key of keys) {
    const candidate = obj[key];
    if (typeof candidate === 'string' && candidate.length > 0) {
      return candidate;
    }
  }

  return fallback;
};
