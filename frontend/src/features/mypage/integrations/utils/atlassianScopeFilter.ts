import type { AtlassianResource } from '../types/sync';

const JIRA_REQUIRED_SCOPE = 'read:jira-work';

/** Jira 후보: read:jira-work scope 포함 */
export const isJiraResource = (resource: AtlassianResource): boolean =>
  resource.scopes.includes(JIRA_REQUIRED_SCOPE);

/** Confluence 후보: Jira가 아닌 나머지 */
export const isConfluenceResource = (resource: AtlassianResource): boolean =>
  !isJiraResource(resource);
