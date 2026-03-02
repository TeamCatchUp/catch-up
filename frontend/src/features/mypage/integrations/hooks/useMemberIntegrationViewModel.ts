import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { INTEGRATION_ACCOUNTS } from '../constants/integrations';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { PreMappingInfo, SyncFilterType, UserSyncItem } from '../types/api';
import type {
  IntegrationService,
  MemberIntegrationCardItem,
  MemberIntegrationRow,
  MemberIntegrationViewModel,
} from '../types/integrations';

/** 매핑 아이템에서 서비스별 PreMappingInfo 추출 */
const getServiceInfo = (item: UserSyncItem, service: IntegrationService): PreMappingInfo | null => {
  switch (service) {
    case 'jira':
    case 'confluence':
      return item.atlassian;
    case 'github':
      return item.github;
    case 'slack':
      return item.slack;
  }
};

/** 이용자 연동 탭에서 필요한 데이터를 userSyncStatus API 기반으로 조합 */
export const useMemberIntegrationViewModel = (params: {
  filterType: SyncFilterType;
  page: number;
  size: number;
}): MemberIntegrationViewModel => {
  const { data: syncStatus, isLoading } = useQuery(adminConnectorQueries.userSyncStatus(params));

  const cards = useMemo<MemberIntegrationCardItem[]>(() => {
    if (!syncStatus) {
      return INTEGRATION_ACCOUNTS.map((account) => ({
        ...account,
        completedCount: 0,
        totalCount: 0,
        completionRate: 0,
      }));
    }

    return INTEGRATION_ACCOUNTS.map((account) => {
      const count = syncStatus.counts[account.service];
      const totalCount = count?.users ?? 0;
      const completedCount = count?.premap ?? 0;
      const completionRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

      return {
        ...account,
        completedCount,
        totalCount,
        completionRate,
      };
    });
  }, [syncStatus]);

  const rows = useMemo<MemberIntegrationRow[]>(() => {
    if (!syncStatus?.items) return [];

    return syncStatus.items.map((item): MemberIntegrationRow => {
      const serviceInfoByService: Partial<Record<IntegrationService, PreMappingInfo>> = {};
      const statusByService = {} as Record<IntegrationService, '미사용' | '완료' | '미등록'>;

      for (const service of ['jira', 'github', 'slack', 'confluence'] as IntegrationService[]) {
        const info = getServiceInfo(item, service);
        if (info) serviceInfoByService[service] = info;
        const hasPremapping = (syncStatus.counts[service]?.premap ?? 0) > 0;
        statusByService[service] = info ? '완료' : hasPremapping ? '미사용' : '미등록';
      }

      return {
        userKey: item.name,
        userName: item.name,
        email: item.email,
        serviceInfoByService,
        statusByService,
      };
    });
  }, [syncStatus]);

  return { cards, rows, total: syncStatus?.total ?? 0, isLoading };
};
