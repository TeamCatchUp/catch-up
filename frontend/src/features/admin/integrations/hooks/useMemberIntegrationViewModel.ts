import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { INTEGRATION_ACCOUNTS } from '../constants/integrationsConfig';
import { MEMBER_TABLE_SERVICES } from '../constants/memberUiConfig';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { PreMappingInfo, SyncFilterType, UserSyncItem } from '../types/integrationApi';
import type {
  IntegrationService,
  MemberIntegrationCardItem,
  MemberIntegrationRow,
  MemberIntegrationViewModel,
} from '../types/integrationModel';

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
    case 'channel_talk':
      return item.channel_talk;
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

        const hasPremapping = (syncStatus.counts[service]?.premap ?? 0) > 0;
        statusByService[service] = info ? '완료' : hasPremapping ? '미사용' : '미등록';
      }

      // confluence는 테이블에 미노출이지만 statusByService 타입(`Record<IntegrationService, ...>`)이 키 강제.
      // cast 정직화 — 미래에 confluence 컬럼 노출되거나 다른 consumer(UserDetailPanel 등)가 lookup 시 undefined 안전.
      statusByService.confluence = '미등록';

      return {
        userKey: item.sub,
        userName: item.name,
        email: item.email,
        serviceInfoByService,
        statusByService,
      };
    });
  }, [syncStatus]);

  return { cards, rows, total: syncStatus?.total ?? 0, isLoading };
};
