import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { INTEGRATION_ACCOUNTS } from '../constants/integrations';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { UserMappingItem } from '../types/api';
import type {
  IntegrationService,
  MemberIntegrationCardItem,
  MemberIntegrationRow,
  MemberIntegrationViewModel,
} from '../types/integrations';

/** 매핑 아이템에서 서비스별 계정 ID 추출 */
const getAccountId = (mapping: UserMappingItem, service: IntegrationService): string | undefined => {
  switch (service) {
    case 'github':
      return mapping.githubLogin ?? undefined;
    case 'jira':
    case 'confluence':
      return mapping.atlassianEmail ?? undefined;
    case 'slack':
      return mapping.slackEmail ?? undefined;
  }
};

/** 이용자 연동 탭에서 필요한 데이터를 userSyncStatus API 기반으로 조합 */
export const useMemberIntegrationViewModel = (): MemberIntegrationViewModel => {
  const { data: syncStatus } = useQuery(adminConnectorQueries.userSyncStatus());

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
    if (!syncStatus?.mappings) return [];

    return syncStatus.mappings
      .map((mapping): MemberIntegrationRow => {
        const accountIdByService: Partial<Record<IntegrationService, string>> = {};
        const statusByService = {} as Record<IntegrationService, '미사용' | '완료' | '미등록'>;

        for (const service of ['jira', 'github', 'slack', 'confluence'] as IntegrationService[]) {
          const id = getAccountId(mapping, service);
          if (id) accountIdByService[service] = id;
          statusByService[service] = id ? '완료' : '미등록';
        }

        return {
          userKey: mapping.name,
          userName: mapping.name,
          email: mapping.atlassianEmail ?? mapping.slackEmail ?? '-',
          phone: '-',
          department: '-',
          teamSizeLabel: '-',
          picture: null,
          accountIdByService,
          statusByService,
        };
      })
      .sort((a, b) => a.userName.localeCompare(b.userName, 'ko'));
  }, [syncStatus]);

  return { cards, rows };
};
