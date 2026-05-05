import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { INTEGRATION_ACCOUNTS } from '../constants/integrationsConfig';
import { MEMBER_TABLE_SERVICES } from '../constants/memberUiConfig';
import { userSourceMappingQueries } from '../queries/userSourceMapping.queries';
import type { SyncFilterType } from '../types/integrationApi';
import type {
  IntegrationService,
  MemberIntegrationCardItem,
  MemberIntegrationRow,
  MemberIntegrationViewModel,
} from '../types/integrationModel';
import type {
  MappedSourceInfo,
  UserSourceMappingItem,
  UserSourceMappingStatus,
} from '../types/userSourceMappingApi';

/**
 * 매핑 아이템에서 서비스별 MappedSourceInfo 추출.
 * 백엔드(PR #610)는 Confluence 매핑을 atlassian 필드로 합쳐 응답하므로 jira/confluence는 모두 atlassian에서 읽음.
 */
const getServiceInfo = (item: UserSourceMappingItem, service: IntegrationService): MappedSourceInfo | null => {
  switch (service) {
    case 'jira':
    case 'confluence':
      return item.atlassian;
    case 'github':
      return item.github;
    case 'slack':
      return item.slack;
    case 'channel_talk':
      return item.channel_talk;
  }
};

/** 이용자 연동 탭에서 필요한 데이터를 user-source-mapping API 두 개로 조합 */
export const useMemberIntegrationViewModel = (params: {
  filterType: SyncFilterType;
  page: number;
  size: number;
}): MemberIntegrationViewModel => {
  // 채널톡 칩은 컬럼 좁힘만 담당 — 백엔드에는 항상 'all'을 전송. 그 외는 그대로 pass-through.
  const mapping_status: UserSourceMappingStatus =
    params.filterType === 'channel_talk' ? 'all' : params.filterType;

  const listQuery = useQuery(
    userSourceMappingQueries.list({ mapping_status, page: params.page, size: params.size }),
  );
  const statusQuery = useQuery(userSourceMappingQueries.status());

  const isLoading = listQuery.isLoading || statusQuery.isLoading;

  const cards = useMemo<MemberIntegrationCardItem[]>(() => {
    if (!statusQuery.data) {
      return INTEGRATION_ACCOUNTS.map((account) => ({
        ...account,
        completedCount: 0,
        totalCount: 0,
        completionRate: 0,
      }));
    }

    return INTEGRATION_ACCOUNTS.map((account) => {
      const count = statusQuery.data[account.service];
      const totalCount = count?.users ?? 0;
      const completedCount = count?.mapped ?? 0;
      const completionRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

      return {
        ...account,
        completedCount,
        totalCount,
        completionRate,
      };
    });
  }, [statusQuery.data]);

  const rows = useMemo<MemberIntegrationRow[]>(() => {
    if (!listQuery.data?.items) return [];

    return listQuery.data.items.map((item): MemberIntegrationRow => {
      const serviceInfoByService: Partial<Record<IntegrationService, MappedSourceInfo>> = {};
      const statusByService = {} as Record<IntegrationService, '미사용' | '완료' | '미등록'>;

      // 이용자 연동 테이블에 노출되는 서비스만 데이터 구성.
      // MEMBER_TABLE_SERVICES를 단일 진실의 원천으로 사용 → 컬럼 변경 시 view model 자동 추적.
      for (const service of MEMBER_TABLE_SERVICES) {
        const info = getServiceInfo(item, service);
        if (info) serviceInfoByService[service] = info;

        if (service === 'channel_talk') {
          // 채널톡은 매니저 기반 매핑이라 '미등록' 상태가 도메인상 존재하지 않음 — 미매핑은 항상 '미사용'으로 표기.
          statusByService[service] = info ? '완료' : '미사용';
          continue;
        }

        const hasMapping = (statusQuery.data?.[service]?.mapped ?? 0) > 0;
        statusByService[service] = info ? '완료' : hasMapping ? '미사용' : '미등록';
      }

      // confluence는 테이블에 미노출이지만 statusByService 타입(`Record<IntegrationService, ...>`)이 키 강제.
      // cast 정직화 — 미래에 confluence 컬럼 노출되거나 다른 consumer(UserDetailPanel 등)가 lookup 시 undefined 안전.
      statusByService.confluence = '미등록';

      return {
        userKey: String(item.user_id),
        sub: item.sub,
        userName: item.name,
        email: item.email,
        serviceInfoByService,
        statusByService,
      };
    });
  }, [listQuery.data, statusQuery.data]);

  return { cards, rows, total: listQuery.data?.total ?? 0, isLoading };
};
