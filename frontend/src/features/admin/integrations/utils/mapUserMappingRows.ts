import type { MappingCellValue, MappingSource, UserMappingRow } from '../types/userMappingModel';
import type { MappedSourceInfo, MappingStatusResponse, UserSourceMappingItem } from '../types/userSourceMappingApi';

/**
 * 목록 응답(snake_case DTO) → 이용자 매핑 표 행. `UserMappingView`에서 추출했다.
 *
 * "미사용" 셀은 응답에 저장 자리가 없어(백엔드 is_ignored는 행 삭제) 직접 복원할 수 없다.
 * develop의 `useMemberIntegrationViewModel`이 쓰던 추론을 이관한다 — 그 서비스에 워크스페이스
 * 매핑이 하나라도 있는데(status counts) 이 사용자만 없으면 '미사용', 서비스 자체가 0건이면
 * 미연동(null). 채널톡은 매니저 기반이라 '미등록' 개념이 없어 미매핑을 항상 '미사용'으로 본다.
 */
export const toMappingCell = (info: MappedSourceInfo | null): MappingCellValue => {
  if (!info) return null;
  if (!info.name && !info.identifier) return null;
  return { name: info.name ?? '-', identifier: info.identifier ?? '', picture: info.picture };
};

/** 계정 정보 없음 → 서비스에 매핑 운영 중이면 '미사용', 아니면 미연동 */
const inferCell = (info: MappedSourceInfo | null, serviceHasMappings: boolean): MappingCellValue =>
  toMappingCell(info) ?? (serviceHasMappings ? 'unused' : null);

const mappedCount = (status: MappingStatusResponse | undefined, key: keyof MappingStatusResponse): number =>
  status?.[key]?.mapped ?? 0;

/** 상태 점(fullyMapped) 판정 대상 — 채널톡은 매니저 전용이라 일반 이용자 감점에서 제외 */
const DOT_SOURCES: readonly MappingSource[] = ['atlassian', 'github', 'slack'];

export const mapUserMappingRow = (
  item: UserSourceMappingItem,
  statusCounts?: MappingStatusResponse,
): UserMappingRow => {
  // atlassian 열은 백엔드가 Jira∪Confluence를 합쳐 응답하므로 운영 여부도 둘의 합으로 본다
  const accounts: Partial<Record<MappingSource, MappingCellValue>> = {
    atlassian: inferCell(
      item.atlassian,
      mappedCount(statusCounts, 'jira') + mappedCount(statusCounts, 'confluence') > 0,
    ),
    github: inferCell(item.github, mappedCount(statusCounts, 'github') > 0),
    slack: inferCell(item.slack, mappedCount(statusCounts, 'slack') > 0),
    channel_talk: toMappingCell(item.channel_talk) ?? 'unused',
  };
  return {
    id: String(item.user_id),
    user: { name: item.name },
    // '미사용'(추론)은 실제 계정이 아니므로 점 판정에서는 미연동과 같게 다룬다 —
    // 백엔드 mapping_status=full(행 존재)과 최대한 같은 방향을 본다
    fullyMapped: DOT_SOURCES.every((source) => {
      const cell = accounts[source];
      return cell != null && cell !== 'unused';
    }),
    accounts,
  };
};

export const mapUserMappingRows = (
  items: readonly UserSourceMappingItem[],
  statusCounts?: MappingStatusResponse,
): UserMappingRow[] => items.map((item) => mapUserMappingRow(item, statusCounts));
