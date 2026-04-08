/** Unix timestamp를 YYYY.MM.DD 형식으로 변환 */
export const formatDate = (unix: number): string => {
  const d = new Date(unix * 1000);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}.${m}.${day}`;
};

/** ISO 날짜 문자열을 MM.DD 형식으로 변환 */
export const formatShortDate = (isoString: string): string => {
  const d = new Date(isoString);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${m}.${day}`;
};

/** ISO 날짜 문자열을 YYYY.MM.DD 형식으로 변환 */
export const formatFullDate = (isoString: string): string => {
  const d = new Date(isoString);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}.${m}.${day}`;
};

/** ISO 날짜 문자열을 상대적 날짜로 변환 (n일 전) */
export const formatRelativeDate = (isoString: string): string => {
  const targetDate = new Date(isoString);
  const today = new Date();

  // 시간 제거 (날짜만 비교)
  targetDate.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);

  const diffTime = today.getTime() - targetDate.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return '오늘';
  if (diffDays === 1) return '어제';
  return `${diffDays}일 전`;
};

/** ISO 날짜 문자열을 상세 상대 시간으로 변환 (N분 전, N시간 전, N일 전) */
export const formatRelativeTime = (isoString: string): string => {
  const now = new Date();
  const target = new Date(isoString);
  const diffMs = now.getTime() - target.getTime();
  const diffMin = Math.floor(diffMs / (1000 * 60));
  const diffHour = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDay = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMin < 1) return '방금 전';
  if (diffMin < 60) return `${diffMin}분 전`;
  if (diffHour < 24) return `${diffHour}시간 전`;
  if (diffDay === 1) return '어제';
  return `${diffDay}일 전`;
};
