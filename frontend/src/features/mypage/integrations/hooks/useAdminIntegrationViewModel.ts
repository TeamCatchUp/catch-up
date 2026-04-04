import { useCallback, useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';

import { INTEGRATION_ACCOUNTS } from '../constants/integrationsConfig';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { AdminIntegrationViewModel, ConnectorDetail, ConnectorResource, IntegrationService } from '../types/integrationModel';
import type { AdminConnectorStatusResponse, ConnectorStatusSource } from '../types/syncModel';

const SOURCE_ORDER: ConnectorStatusSource[] = ['github', 'jira', 'slack', 'confluence'];

const RESOURCE_LABELS: Record<IntegrationService, string> = {
  jira: '임베딩된 Jira Project',
  github: '임베딩된 Repository',
  slack: '임베딩된 Slack 채널',
  confluence: '임베딩된 Confluence Space',
};

/** "YYYY. M. D." 날짜 포맷 */
const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`;
};

/** oldest ~ latest 범위 문자열 */
const formatRange = (oldest: string | null, latest: string | null): string => {
  if (!oldest && !latest) return '-';
  return `${formatDate(oldest)} ~ ${formatDate(latest)}`;
};

/** 관리자 연동 화면에서 필요한 데이터를 조합해 반환 */
export const useAdminIntegrationViewModel = (): AdminIntegrationViewModel => {
  const statusQueries = useQueries({
    queries: SOURCE_ORDER.map((source) => adminConnectorQueries.connectorTargetStatus(source)),
  });

  const statusMap = useMemo<Record<IntegrationService, AdminConnectorStatusResponse | undefined>>(() => {
    const map: Record<string, AdminConnectorStatusResponse | undefined> = {};
    SOURCE_ORDER.forEach((source, i) => {
      map[source] = statusQueries[i]?.data;
    });
    return map as Record<IntegrationService, AdminConnectorStatusResponse | undefined>;
  }, [statusQueries]);

  const integrationMenu = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((item) => ({
        ...item,
        actionText: `${item.name} 연동하기`,
        connected: (statusMap[item.service]?.total_targets ?? 0) > 0,
      })),
    [statusMap],
  );

  const getConnectorDetail = useCallback(
    (service: IntegrationService): ConnectorDetail => {
      const status = statusMap[service];
      const targets = status?.targets ?? [];

      // 전체 데이터 범위: 모든 target 중 가장 오래된 oldest ~ 가장 최신 latest
      const allOldest = targets.map((t) => t.oldest).filter(Boolean) as string[];
      const allLatest = targets.map((t) => t.latest).filter(Boolean) as string[];
      const globalOldest = allOldest.length ? allOldest.sort()[0] : null;
      const globalLatest = allLatest.length ? allLatest.sort().reverse()[0] : null;

      const resources: ConnectorResource[] = targets.map((t) => ({
        name: t.target_name,
        dateRange: formatRange(t.oldest, t.latest),
      }));

      return {
        connected: targets.length > 0,
        dataRange: formatRange(globalOldest, globalLatest),
        resources,
        resourceLabel: RESOURCE_LABELS[service],
      };
    },
    [statusMap],
  );

  return {
    integrationMenu,
    getConnectorDetail,
    isLoading: statusQueries.some((q) => q.isLoading),
  };
};
