import type { ConnectorStatusSource, SyncConnector } from '../types/syncModel';

/**
 * 모든 연동 화면에서 공통으로 사용하는 connector 표시 순서.
 *
 * 이전에는 5곳(`useEmbeddingJobs`, `useEmbeddingHistory`, `useAdminIntegrationViewModel`,
 * `EmbeddingProgressPanel`, `IntegrationsSection`)에 각자 정의되어 있어 순서가 drift할 위험이
 * 있었음 (실제로 jira/github 순서가 두 hook에서 달랐음). 신규 connector 추가 시 이 한 곳만 수정.
 */
export const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence', 'channel_talk'];

/**
 * 임베딩 히스토리 API(`GET /admin/connector/status?source=`)의 source 순서.
 * `SyncConnector`와 동일 값이지만 별도 type alias라 type-safe import용으로 분리.
 */
export const CONNECTOR_STATUS_SOURCE_ORDER: ConnectorStatusSource[] = [
  'jira',
  'github',
  'slack',
  'confluence',
  'channel_talk',
];

/**
 * 단일 scope를 사용하는 connector (채널톡 제외).
 * 채널톡만 N개 channel scope를 동시 추적하므로 별도 처리.
 */
export const SINGLE_SCOPE_CONNECTORS: Exclude<SyncConnector, 'channel_talk'>[] = [
  'jira',
  'github',
  'slack',
  'confluence',
];
