import type { MappingCellValue, MappingSource, UserMappingRow } from '../types/userMappingModel';
import { MAPPING_SOURCES } from '../types/userMappingModel';
import type { MappedSourceInfo, UserSourceMappingItem } from '../types/userSourceMappingApi';

/**
 * 목록 응답(snake_case DTO) → 이용자 매핑 표 행. `UserMappingView`에서 추출했다.
 *
 * 알려진 제약: 응답 `MappedSourceInfo`에 `is_ignored` 대응 필드가 없어 저장된
 * "미사용" 선언을 셀 값 `'unused'`로 복원할 수 없다 — 새로고침 뒤에는 미연동("-")
 * 으로 보인다. 백엔드가 플래그를 내려주기 전까지는 표시 한계다.
 */
export const toMappingCell = (info: MappedSourceInfo | null): MappingCellValue => {
  if (!info) return null;
  if (!info.name && !info.identifier) return null;
  return { name: info.name ?? '-', identifier: info.identifier ?? '', picture: info.picture };
};

export const mapUserMappingRow = (item: UserSourceMappingItem): UserMappingRow => {
  const accounts: Partial<Record<MappingSource, MappingCellValue>> = {
    atlassian: toMappingCell(item.atlassian),
    github: toMappingCell(item.github),
    slack: toMappingCell(item.slack),
    channel_talk: toMappingCell(item.channel_talk),
  };
  return {
    id: String(item.user_id),
    user: { name: item.name },
    fullyMapped: MAPPING_SOURCES.every((source) => accounts[source] != null),
    accounts,
  };
};

export const mapUserMappingRows = (items: readonly UserSourceMappingItem[]): UserMappingRow[] =>
  items.map(mapUserMappingRow);
