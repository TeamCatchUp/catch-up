import { useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { INTEGRATION_ACCOUNTS } from '../constants/integrations';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { ConnectorStatusBase } from '../types/api';
import type { AdminIntegrationViewModel, ConnectorDetail, IntegrationService } from '../types/integrations';

const RESOURCE_LABELS: Record<IntegrationService, string> = {
  jira: '연동된 Jira Project',
  github: '연동된 Repository',
  slack: 'Catch Up Slack Bot이 추가된 채널',
  confluence: '연동된 Confluence Space',
};

/** ISO 날짜 → "YYYY. M. D. HH:mm" */
const formatDate = (iso: string | null): string => {
  if (!iso) return '-';
  const d = new Date(iso);
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}. ${h}:${min}`;
};

/** oldest ~ latest 범위 문자열 */
const formatRange = (status: ConnectorStatusBase | undefined): string => {
  if (!status?.oldest || !status?.latest) return '-';
  return `${formatDate(status.oldest)} ~ ${formatDate(status.latest)}`;
};

/** 커넥터 상태에서 리소스 목록 추출 */
const getResources = (status: unknown): string[] => {
  if (!status || typeof status !== 'object') return [];
  if ('repositories' in status) return (status as { repositories: string[] }).repositories;
  if ('projects' in status) return (status as { projects: string[] }).projects;
  if ('channels' in status) return (status as { channels: string[] }).channels;
  if ('spaces' in status) return (status as { spaces: string[] }).spaces;
  return [];
};

/** 관리자 연동 화면에서 필요한 데이터를 조합해 반환 */
export const useAdminIntegrationViewModel = (): AdminIntegrationViewModel => {
  const { data: github, isLoading: githubLoading } = useQuery(adminConnectorQueries.githubStatus());
  const { data: jira, isLoading: jiraLoading } = useQuery(adminConnectorQueries.jiraStatus());
  const { data: slack, isLoading: slackLoading } = useQuery(adminConnectorQueries.slackStatus());
  const { data: confluence, isLoading: confluenceLoading } = useQuery(adminConnectorQueries.confluenceStatus());

  const statusMap = useMemo<Record<IntegrationService, ConnectorStatusBase | undefined>>(
    () => ({ github, jira, slack, confluence }),
    [github, jira, slack, confluence],
  );

  const integrationMenu = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((item) => ({
        ...item,
        actionText: `${item.name} 연동하기`,
        connected: statusMap[item.service]?.connected ?? false,
      })),
    [statusMap],
  );

  const getConnectorDetail = useCallback(
    (service: IntegrationService): ConnectorDetail => {
      const status = statusMap[service];
      return {
        connected: status?.connected ?? false,
        dataRange: formatRange(status),
        resources: getResources(status),
        resourceLabel: RESOURCE_LABELS[service],
      };
    },
    [statusMap],
  );

  return {
    integrationMenu,
    getConnectorDetail,
    isLoading: githubLoading || jiraLoading || slackLoading || confluenceLoading,
  };
};
