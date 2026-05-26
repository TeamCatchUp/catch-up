// 보안: javascript:, data: 등 위험 스킴 차단. http/https만 허용.

export const ALLOWED_URL_SCHEMES = ['http:', 'https:'] as const;

export function isSafeUrl(raw: string | null | undefined): boolean {
  if (!raw) return false;
  try {
    const parsed = new URL(raw);
    return (ALLOWED_URL_SCHEMES as readonly string[]).includes(parsed.protocol);
  } catch {
    return false;
  }
}
