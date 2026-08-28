import { useCallback, useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { CONNECTOR_STATUS_SOURCE_ORDER } from '../constants/connectorOrder';
import { INTEGRATION_ACCOUNTS } from '../constants/integrationsConfig';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type {
  AdminIntegrationViewModel,
  ConnectorDetail,
  ConnectorDetailStatus,
  ConnectorResource,
  IntegrationService,
} from '../types/integrationModel';
import type { AdminConnectorStatusResponse } from '../types/syncModel';
import { buildChannelTalkResourceTree } from '../utils/buildChannelTalkResourceTree';
import { formatEmbeddingRange } from '../utils/embeddingUtils';
import { isCompletedSyncTarget } from '../utils/isCompletedSyncTarget';
import { type ConnectorQueryFlags, resolveConnectorStatus } from '../utils/resolveConnectorStatus';
import { syncTargetKey } from '../utils/syncTargetKey';

// 단일 source 통합. 이전엔 이 파일이 'github, jira, ...' 순서였고 useEmbeddingHistory는 'jira, github, ...'
// 순서로 drift되어 있었음 — constants/connectorOrder.ts로 정렬 통일.
const SOURCE_ORDER = CONNECTOR_STATUS_SOURCE_ORDER;

const RESOURCE_LABELS: Record<IntegrationService, string> = {
  jira: '임베딩된 Jira Project',
  github: '임베딩된 Repository',
  slack: '임베딩된 Slack 채널',
  confluence: '임베딩된 Confluence Space',
  channel_talk: '연결된 채널톡 채널',
};

/** 관리자 연동 화면에서 필요한 데이터를 조합해 반환 */
export const useAdminIntegrationViewModel = (): AdminIntegrationViewModel => {
  // dataRange/resources용 — 임베딩된 target 정보
  const statusQueries = useQueries({
    queries: SOURCE_ORDER.map((source) => adminConnectorQueries.connectorTargetStatus(source)),
  });

  // connected 판별용 — OAuth/설치 완료 여부 (임베딩 0개여도 연동됨 표시)
  // canonical connection-status는 connected 플래그 + count를 제공하므로 별 분기 없이 connected만 보면 됨.
  const atlassianStatus = useQuery(adminConnectorQueries.connectionStatus('atlassian'));
  const slackStatus = useQuery(adminConnectorQueries.connectionStatus('slack'));
  const githubStatus = useQuery(adminConnectorQueries.connectionStatus('github'));
  const channelTalkStatus = useQuery(adminConnectorQueries.connectionStatus('channel_talk'));

  const isServiceConnected = useCallback(
    (service: IntegrationService): boolean => {
      switch (service) {
        case 'jira':
        case 'confluence':
          return atlassianStatus.data?.connected === true;
        case 'github':
          return githubStatus.data?.connected === true;
        case 'slack':
          return slackStatus.data?.connected === true;
        case 'channel_talk':
          return channelTalkStatus.data?.connected === true;
      }
    },
    [atlassianStatus.data, slackStatus.data, githubStatus.data, channelTalkStatus.data],
  );

  /**
   * 연동 조직·워크스페이스의 대표 이름 — connection-status `items[].name`.
   * jira/confluence는 atlassian OAuth 하나를 공유하므로 같은 사이트명을 쓴다.
   * 채널톡은 워크스페이스 개념이 없고 채널 credential이 N개라 첫 채널명을 대표로 삼는다
   * (여러 채널일 때의 표기는 Figma에 근거가 없다).
   */
  const getWorkspaceName = useCallback(
    (service: IntegrationService): string | null => {
      switch (service) {
        case 'jira':
        case 'confluence':
          return atlassianStatus.data?.items?.[0]?.name ?? null;
        case 'github':
          return githubStatus.data?.items?.[0]?.name ?? null;
        case 'slack':
          return slackStatus.data?.items?.[0]?.name ?? null;
        case 'channel_talk': {
          const items = channelTalkStatus.data?.vendor === 'channel_talk' ? channelTalkStatus.data.items : [];
          return items.find((item) => item.metadata.credential_type === 'channel')?.name ?? null;
        }
      }
    },
    [atlassianStatus.data, githubStatus.data, slackStatus.data, channelTalkStatus.data],
  );

  const statusMap = useMemo<Record<IntegrationService, AdminConnectorStatusResponse | undefined>>(() => {
    const map: Record<string, AdminConnectorStatusResponse | undefined> = {};
    SOURCE_ORDER.forEach((source, i) => {
      map[source] = statusQueries[i]?.data;
    });
    return map as Record<IntegrationService, AdminConnectorStatusResponse | undefined>;
  }, [statusQueries]);

  // 서비스 → connection-status 쿼리 매핑. jira/confluence는 atlassian 하나를 공유한다.
  const connectionFlagsByService = useMemo<Record<IntegrationService, ConnectorQueryFlags>>(
    () => ({
      jira: { isLoading: atlassianStatus.isLoading, isError: atlassianStatus.isError },
      confluence: { isLoading: atlassianStatus.isLoading, isError: atlassianStatus.isError },
      github: { isLoading: githubStatus.isLoading, isError: githubStatus.isError },
      slack: { isLoading: slackStatus.isLoading, isError: slackStatus.isError },
      channel_talk: { isLoading: channelTalkStatus.isLoading, isError: channelTalkStatus.isError },
    }),
    [atlassianStatus, githubStatus, slackStatus, channelTalkStatus],
  );

  // 서비스 → target-status 쿼리 매핑. SOURCE_ORDER 인덱스로 statusQueries와 대응한다.
  const targetFlagsByService = useMemo<Record<IntegrationService, ConnectorQueryFlags>>(() => {
    const map: Record<string, ConnectorQueryFlags> = {};
    SOURCE_ORDER.forEach((source, i) => {
      const q = statusQueries[i];
      map[source] = { isLoading: q?.isLoading ?? true, isError: q?.isError ?? false };
    });
    return map as Record<IntegrationService, ConnectorQueryFlags>;
  }, [statusQueries]);

  const getStatus = useCallback(
    (service: IntegrationService): ConnectorDetailStatus =>
      resolveConnectorStatus(connectionFlagsByService[service], targetFlagsByService[service]),
    [connectionFlagsByService, targetFlagsByService],
  );

  const integrationMenu = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((item) => ({
        ...item,
        actionText: `${item.name} 연동하기`,
        connected: isServiceConnected(item.service),
        status: getStatus(item.service),
        workspaceName: getWorkspaceName(item.service),
      })),
    [isServiceConnected, getStatus, getWorkspaceName],
  );

  const getConnectorDetail = useCallback(
    (service: IntegrationService): ConnectorDetail => {
      const status = statusMap[service];
      const allTargets = status?.targets ?? [];
      /*
       * 응답 targets는 "연결됨 ∪ 이력 있음"이라 임베딩된 적 없는 target이
       * sync_status:"pending", event_id:"" 합성 행으로 섞여 온다.
       * "임베딩된 X" 표와 데이터 범위는 완료(success/failed) 이력이 있는 것만 쓴다 —
       * 채널톡만 라벨이 "연결된 채널"이라 연결만 된 채널도 트리에 남긴다.
       */
      const embedded = allTargets.filter(isCompletedSyncTarget);

      // 전체 데이터 범위: 임베딩된 target 중 가장 오래된 oldest ~ 가장 최신 latest
      const allOldest = embedded.map((t) => t.oldest).filter(Boolean) as string[];
      const allLatest = embedded.map((t) => t.latest).filter(Boolean) as string[];
      const globalOldest = allOldest.length ? allOldest.sort()[0] : null;
      const globalLatest = allLatest.length ? allLatest.sort().reverse()[0] : null;

      // 채널톡만 채널 → 도큐먼트 스페이스 2단이다. 나머지는 계층이 없어 평면.
      const resources: ConnectorResource[] =
        service === 'channel_talk'
          ? buildChannelTalkResourceTree(allTargets)
          : embedded.map((t) => ({
              id: syncTargetKey(t),
              name: t.target_name,
              dateRange: formatEmbeddingRange(t.oldest, t.latest),
            }));

      return {
        status: getStatus(service),
        connected: isServiceConnected(service),
        dataRange: formatEmbeddingRange(globalOldest, globalLatest),
        resources,
        resourceLabel: RESOURCE_LABELS[service],
        workspaceName: getWorkspaceName(service),
      };
    },
    [statusMap, isServiceConnected, getStatus, getWorkspaceName],
  );

  return {
    integrationMenu,
    getConnectorDetail,
  };
};
