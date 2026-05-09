import type { AtlassianConnectionMetadata } from '../types/connectionStatusApi';

const JIRA_REQUIRED_SCOPE = 'read:jira-work';

// SSoT: backend/catchup/connectors/atlassian/constants.py REQUIRED_CONFLUENCE_SCOPES.
// 백엔드는 callback_service._persist_tokens_sync에서 이 9개 scope의 issubset 여부로
// confluence 연결 성공을 판정한다. 단일 OAuth 토큰이 jira+confluence scope를 함께
// 가지는 게 일반적이라 negative 매처(`!isJiraScope`)로는 confluence를 구분할 수 없다.
const CONFLUENCE_REQUIRED_SCOPES: readonly string[] = [
  'read:confluence-content.all',
  'read:confluence-space.summary',
  'read:confluence-user',
  'read:space:confluence',
  'read:space.permission:confluence',
  'read:page:confluence',
  'read:blogpost:confluence',
  'read:comment:confluence',
  'read:attachment:confluence',
];

/** Jira 후보: read:jira-work scope 포함 */
export const isJiraScope = (metadata: AtlassianConnectionMetadata): boolean =>
  metadata.scopes.includes(JIRA_REQUIRED_SCOPE);

/** Confluence 후보: 백엔드 REQUIRED_CONFLUENCE_SCOPES 전체를 포함 */
export const isConfluenceScope = (metadata: AtlassianConnectionMetadata): boolean =>
  CONFLUENCE_REQUIRED_SCOPES.every((scope) => metadata.scopes.includes(scope));
