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
