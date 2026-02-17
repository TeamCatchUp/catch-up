import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_MEMBER_STATUS_PATTERNS, REQUIRED_MOCK_MEMBER_STATUSES } from '@/shared/mocks/integration';

import type { IntegrationService, MemberIntegrationRow, MemberIntegrationStatus } from '../types/integrations';
import type { MemberDisplayRow } from '../types/memberDisplay';

const toMemberStatus = (value: string): MemberIntegrationStatus => value as MemberIntegrationStatus;

const toMemberStatusRecord = (
  pattern: (typeof MOCK_MEMBER_STATUS_PATTERNS)[number],
): Record<IntegrationService, MemberIntegrationStatus> => ({
  jira: toMemberStatus(pattern.jira),
  github: toMemberStatus(pattern.github),
  slack: toMemberStatus(pattern.slack),
  confluence: toMemberStatus(pattern.confluence),
});

/** 이용자 연동 테이블 행을 UI 렌더용 모델로 변환 */
export const buildMemberDisplayRows = (
  rows: MemberIntegrationRow[],
  tableServices: IntegrationService[],
): MemberDisplayRow[] => {
  if (rows.length === 0) return [];

  // 실제 API 모드: 가공 없이 그대로 반환
  if (!USE_MOCK) {
    return rows.map((row) => ({
      renderKey: row.userKey,
      row,
      displayStatusByService: row.statusByService,
    }));
  }

  // Mock 모드: 행 복제 없이 실제 row만 사용하고, 필요 시 상태 패턴만 보정
  const displayRows = rows.map((row) => ({ renderKey: row.userKey, row }));

  const existingStatuses = new Set<MemberIntegrationStatus>(
    rows.flatMap((row) => tableServices.map((service) => row.statusByService[service])),
  );
  const requiredStatuses = REQUIRED_MOCK_MEMBER_STATUSES as readonly MemberIntegrationStatus[];
  const shouldApplyMockStatuses = requiredStatuses.some((status) => !existingStatuses.has(status));

  return displayRows.map(({ renderKey, row }, index) => ({
    renderKey,
    row,
    displayStatusByService: shouldApplyMockStatuses
      ? toMemberStatusRecord(MOCK_MEMBER_STATUS_PATTERNS[index % MOCK_MEMBER_STATUS_PATTERNS.length])
      : row.statusByService,
  }));
};
