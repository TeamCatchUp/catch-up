import { useQuery } from '@tanstack/react-query';

import type { IntegrationService } from '@/shared/types/integrationService';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { SyncConnector } from '../types/syncModel';
import { isConfluenceResource, isJiraResource } from '../utils/atlassianScopeFilter';

/**
 * 서비스별 scope_id를 자동으로 획득하는 훅.
 * scope는 1개 전제 → 첫 번째 값 자동 선택.
 */
export const useScopeId = (service: IntegrationService) => {
  const connector = service as SyncConnector;

  const githubQuery = useQuery({
    ...adminConnectorQueries.githubInstallations(),
    enabled: service === 'github',
  });

  const slackQuery = useQuery({
    ...adminConnectorQueries.slackInstallationStatus(),
    enabled: service === 'slack',
  });

  const atlassianQuery = useQuery({
    ...adminConnectorQueries.atlassianInstallationStatus(),
    enabled: service === 'jira' || service === 'confluence',
  });

  const getScopeId = (): string | null => {
    switch (connector) {
      case 'github': {
        const installation = githubQuery.data?.[0];
        return installation ? String(installation.installation_id) : null;
      }
      case 'slack': {
        const workspace = slackQuery.data?.workspaces?.[0];
        return workspace?.team_id ?? null;
      }
      case 'jira': {
        const resource = atlassianQuery.data?.resources?.find(isJiraResource);
        return resource?.id ?? null;
      }
      case 'confluence': {
        const resource = atlassianQuery.data?.resources?.find(isConfluenceResource);
        return resource?.id ?? null;
      }
    }
  };

  const isLoading = (() => {
    switch (connector) {
      case 'github':
        return githubQuery.isLoading;
      case 'slack':
        return slackQuery.isLoading;
      case 'jira':
      case 'confluence':
        return atlassianQuery.isLoading;
    }
  })();

  return {
    scopeId: getScopeId(),
    isLoading,
  };
};
