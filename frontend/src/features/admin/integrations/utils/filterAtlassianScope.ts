import type { AtlassianConnectionMetadata } from '../types/connectionStatusApi';

const JIRA_REQUIRED_SCOPE = 'read:jira-work';

/** Jira 후보: read:jira-work scope 포함 */
export const isJiraScope = (metadata: AtlassianConnectionMetadata): boolean =>
  metadata.scopes.includes(JIRA_REQUIRED_SCOPE);

/** Confluence 후보: Jira가 아닌 나머지 */
export const isConfluenceScope = (metadata: AtlassianConnectionMetadata): boolean => !isJiraScope(metadata);
