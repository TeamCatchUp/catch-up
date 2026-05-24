// ISO datetime → "YYYY-MM-DD HH:MM AM/PM" 형식. 파싱 불가하면 원문 그대로.
// FormContent 의 폼 제출 시각 표시용. 로컬 시간 기준.

export function formatSubmittedAt(value: string | undefined): string | null {
  const raw = value?.trim();
  if (!raw) return null;

  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  const day = String(parsed.getDate()).padStart(2, '0');
  const hour24 = parsed.getHours();
  const meridiem = hour24 < 12 ? 'AM' : 'PM';
  const hour12 = String(hour24 % 12 || 12).padStart(2, '0');
  const minute = String(parsed.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour12}:${minute} ${meridiem}`;
}
