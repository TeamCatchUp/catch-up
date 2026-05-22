// OriginalMessageItem[] 을 created_at 캘린더 날짜별로 그룹핑하는 순수 util.
// 입력 순서를 보존하며 각 날짜 그룹을 처음 등장한 순서대로 반환한다.
// created_at 이 null 인 메시지는 날짜를 알 수 없어 맨 뒤 그룹으로 모은다.

import type { OriginalMessageItem } from '@/features/hybrid-search/types/originalApi';

export interface MessageDateGroup {
  // 그룹 대표 날짜 — DateIndicator 가 파싱하는 ISO 날짜 문자열.
  // created_at 이 모두 null 인 그룹은 빈 문자열 (DateIndicator 는 빈 문자열에 아무것도 렌더하지 않음).
  date: string;
  items: OriginalMessageItem[];
}

// ISO datetime → 로컬 캘린더 날짜(YYYY-MM-DD). 파싱 불가하면 null.
// DateIndicator 와 동일하게 로컬 시간 기준으로 날짜를 가른다.
function toCalendarDate(value: string): string | null {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  const day = String(parsed.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const UNDATED_KEY = '';

export function groupMessagesByDate(items: OriginalMessageItem[]): MessageDateGroup[] {
  const groups: MessageDateGroup[] = [];
  const indexByKey = new Map<string, number>();

  for (const item of items) {
    const key = (item.created_at && toCalendarDate(item.created_at)) || UNDATED_KEY;

    const existingIndex = indexByKey.get(key);
    if (existingIndex !== undefined) {
      groups[existingIndex] = {
        ...groups[existingIndex],
        items: [...groups[existingIndex].items, item],
      };
      continue;
    }

    indexByKey.set(key, groups.length);
    groups.push({ date: key, items: [item] });
  }

  // 날짜 미상(null created_at) 그룹은 항상 맨 뒤로 보낸다.
  const undatedIndex = groups.findIndex((group) => group.date === UNDATED_KEY);
  if (undatedIndex !== -1 && undatedIndex !== groups.length - 1) {
    const [undated] = groups.splice(undatedIndex, 1);
    groups.push(undated);
  }

  return groups;
}
