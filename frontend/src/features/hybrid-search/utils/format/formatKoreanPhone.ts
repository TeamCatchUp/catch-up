// 한국 전화번호 포맷터 — 다양한 raw 형식을 '+82 AREA-MIDDLE-LAST' 로 정규화.
// 입력 예: '010-1234-5678' / '01012345678' / '+82 10-1234-5678' / '02-789-0123' / '031-1234-5678'
// 출력 예: '+82 10-1234-5678' / '+82 2-789-0123' / '+82 31-1234-5678'
//
// 처리 규칙:
// 1) digit 만 추출
// 2) '82' 시작 → 그 뒤를 national 로 / '0' 시작 → 0 제거 / 그 외 → 그대로 national
// 3) area code 식별: 1X (mobile) = 2자리, 2 (서울) = 1자리, 그 외 = 2자리
// 4) subscriber 8자리 → 4+4, 7자리 → 3+4
// 5) 식별 불가/숫자 없음 → 원본 trim 그대로 반환 (포맷 실패 시 데이터 보존)

export function formatKoreanPhone(raw: string | undefined | null): string | undefined {
  if (raw == null) return undefined;
  const trimmed = raw.trim();
  if (!trimmed) return undefined;

  const digits = trimmed.replace(/\D/g, '');
  if (!digits) return trimmed;

  let national: string;
  if (digits.startsWith('82')) national = digits.slice(2);
  else if (digits.startsWith('0')) national = digits.slice(1);
  else national = digits;

  if (!national) return trimmed;

  let areaLen: number;
  if (national.startsWith('1')) areaLen = 2; // 모바일 (10, 11, 16~19)
  else if (national.startsWith('2')) areaLen = 1; // 서울
  else areaLen = 2; // 그 외 지역 (031, 051 등)

  const area = national.slice(0, areaLen);
  const subscriber = national.slice(areaLen);

  if (subscriber.length === 0) return `+82 ${area}`;

  let subGroups: string[];
  if (subscriber.length === 8) subGroups = [subscriber.slice(0, 4), subscriber.slice(4)];
  else if (subscriber.length === 7) subGroups = [subscriber.slice(0, 3), subscriber.slice(3)];
  else return trimmed; // 예상 외 길이 — 원본 보존

  return `+82 ${area}-${subGroups.join('-')}`;
}
