import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { MOCK_INTEGRATION_LAST_SYNC_AT, MOCK_INTEGRATION_SPACE_ROWS } from '@/shared/mocks/integration/data';
import { integrationQueries } from '@/shared/queries/integration.queries';

import { INTEGRATION_ACCOUNTS } from '../constants/integrations.constants';
import type { AdminIntegrationViewModel, IntegrationService } from '../types/integrations.types';
import { parseConnected } from '../utils/integration.parsers';

/** 관리자 연동 화면에서 필요한 데이터를 조합해 반환 */
export const useAdminIntegrationViewModel = (): AdminIntegrationViewModel => {
  const { data: jiraStatus } = useQuery(integrationQueries.jira.status());
  const cloudId = (jiraStatus as { resources?: { id: string }[] })?.resources?.[0]?.id ?? '';
  const { data: jiraSyncStatus } = useQuery(integrationQueries.jira.syncStatus(cloudId));
  const { data: slackStatus } = useQuery(integrationQueries.slack.status());
  const { data: githubInstallations } = useQuery(integrationQueries.github.installations());

  const serviceConnected = useMemo<Record<IntegrationService, boolean>>(
    () => ({
      jira: parseConnected(jiraStatus, true),
      github: parseConnected(githubInstallations, true),
      slack: parseConnected(slackStatus, true),
      confluence: false,
    }),
    [jiraStatus, githubInstallations, slackStatus],
  );

  const lastSyncedAt = useMemo(() => {
    if (!Array.isArray(jiraSyncStatus) || jiraSyncStatus.length === 0) {
      return MOCK_INTEGRATION_LAST_SYNC_AT;
    }
    const dates = jiraSyncStatus
      .map((s: { last_successful_sync_at?: string | null }) => s.last_successful_sync_at)
      .filter((d): d is string => !!d);
    if (dates.length === 0) return MOCK_INTEGRATION_LAST_SYNC_AT;
    return dates.sort().at(-1) ?? MOCK_INTEGRATION_LAST_SYNC_AT;
  }, [jiraSyncStatus]);

  const integrationMenu = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((item) => ({
        ...item,
        actionText: `${item.name} 연동하기`,
        connected: serviceConnected[item.service],
      })),
    [serviceConnected],
  );

  return {
    integrationMenu,
    lastSyncedAt,
    spaceRows: MOCK_INTEGRATION_SPACE_ROWS,
  };
};
