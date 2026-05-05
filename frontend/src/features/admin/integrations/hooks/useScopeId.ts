import { useQuery } from '@tanstack/react-query';

import type { IntegrationService } from '@/shared/types/integrationService';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { ConnectorVendor } from '../types/connectionStatusApi';
import { isConfluenceScope, isJiraScope } from '../utils/filterAtlassianScope';

/**
 * 서비스별 scope_id를 자동으로 획득하는 훅.
 * canonical `connection-status` 단일 호출 후 vendor에 맞춰 첫 항목의 id를 추출.
 * jira/confluence는 atlassian endpoint를 공유해 호출하고 metadata.scopes로 분리.
 * channel_talk는 multi-scope이므로 이 훅 경로로 진입하지 않는다 (ChannelTalkEmbeddingModal에서 직접 처리).
 */
export const useScopeId = (service: IntegrationService) => {
  const vendor: ConnectorVendor =
    service === 'jira' || service === 'confluence' ? 'atlassian' : (service as ConnectorVendor);

  const query = useQuery({
    ...adminConnectorQueries.connectionStatus(vendor),
    enabled: service !== 'channel_talk',
  });

  const scopeId = ((): string | null => {
    const data = query.data;
    if (!data) return null;
    if (data.vendor === 'atlassian' || data.vendor === 'jira' || data.vendor === 'confluence') {
      if (service === 'jira') return data.items.find((item) => isJiraScope(item.metadata))?.id ?? null;
      if (service === 'confluence') return data.items.find((item) => isConfluenceScope(item.metadata))?.id ?? null;
    }
    return data.items[0]?.id ?? null;
  })();

  return {
    scopeId,
    isLoading: query.isLoading,
  };
};
