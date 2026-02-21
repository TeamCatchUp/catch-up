import type { IntegrationService } from '@/shared/types/integrationService';

// ─── Connector Status ───

/** 커넥터 상태 공통 필드 */
export interface ConnectorStatusBase {
  tool_name: string;
  connected: boolean;
  oldest: string | null;
  latest: string | null;
}

export interface GithubConnectorStatus extends ConnectorStatusBase {
  tool_name: 'github';
  repositories: string[];
}

export interface JiraConnectorStatus extends ConnectorStatusBase {
  tool_name: 'jira';
  projects: string[];
}

export interface SlackConnectorStatus extends ConnectorStatusBase {
  tool_name: 'slack';
  channels: string[];
}

export interface ConfluenceConnectorStatus extends ConnectorStatusBase {
  tool_name: 'confluence';
  spaces: string[];
}

export type ConnectorStatus =
  | GithubConnectorStatus
  | JiraConnectorStatus
  | SlackConnectorStatus
  | ConfluenceConnectorStatus;

// ─── User Sync Status ───

export interface UserSyncCount {
  users: number;
  premap: number;
}

export interface UserMappingItem {
  name: string;
  githubLogin: string | null;
  atlassianEmail: string | null;
  slackEmail: string | null;
}

export interface UserSyncStatusResponse {
  counts: Record<IntegrationService, UserSyncCount>;
  mappings: UserMappingItem[];
}

// ─── Syncable Entities ───

export interface SyncableJiraProject {
  project_key: string;
  project_name: string;
}

export interface SyncableGithubRepo {
  full_name: string;
  repo_id: number;
}

export interface SyncableConfluenceSpace {
  space_name: string;
  space_key: string;
}

export type SyncableEntity = SyncableJiraProject | SyncableGithubRepo | SyncableConfluenceSpace;

/** syncable API 응답: Record<cloud_id|installation_id, entity[]> */
export type SyncableResponse<T extends SyncableEntity = SyncableEntity> = Record<string, T[]>;

// ─── Sync Full Request ───

export interface GithubSyncFullRequest {
  installation_id: number;
  repo_ids: number[] | null;
  sync_days: number | null;
}

export interface JiraSyncFullRequest {
  cloud_id: string;
  project_keys: string[] | null;
  sync_days: number | null;
}

export interface SlackSyncFullRequest {
  team_id: string;
  sync_days: number | null;
}

export interface ConfluenceSyncFullRequest {
  cloud_id: string;
  space_keys: string[] | null;
  sync_days: number | null;
}
