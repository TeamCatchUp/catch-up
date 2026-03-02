import type { IntegrationService } from '@/shared/types/integrationService';

// ─── Vendor Type ───

export type VendorType = 'github' | 'slack' | 'atlassian';

// ─── Mapping Upload ───

export interface MappingUploadStats {
  csv_rows_skipped: number;
  total_success: number;
  total_failed: number;
  new_mappings: number;
  updated_mappings: number;
}

export interface MappingUploadResponse {
  status: string;
  file_type: string;
  stats: MappingUploadStats;
}

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

export interface PreMappingInfo {
  name: string | null;
  email: string | null;
  picture: string | null;
}

export interface UserSyncItem {
  name: string;
  email: string;
  atlassian: PreMappingInfo | null;
  slack: PreMappingInfo | null;
  github: PreMappingInfo | null;
}

export type SyncFilterType = 'all' | 'full' | 'partial';

export interface UserSyncStatusResponse {
  total: number;
  page: number;
  size: number;
  counts: Record<IntegrationService, UserSyncCount>;
  items: UserSyncItem[];
}

// ─── Sync Status (임베딩 진행 상태) ───

export type SyncStatusValue = 'pending' | 'in_progress' | 'success' | 'failed';

/** GitHub: 엔티티별(issue/pr/commit) 동기화 상태 */
export interface GithubEntitySyncState {
  status: SyncStatusValue | null;
  synced_count: number;
  total_count: number;
  last_sync_at: string | null;
  last_successful_sync_at: string | null;
  error: string | null;
}

/** GitHub: 레포별 동기화 상태 */
export interface GithubRepoSyncStatus {
  repository: string;
  entities: Record<string, GithubEntitySyncState>;
}

/** GET /api/v1/github/sync/status/{installation_id} */
export interface GithubSyncStatusResponse {
  installation_id: number;
  repositories: GithubRepoSyncStatus[];
}

/** Jira/Slack/Confluence 공통 동기화 상태 항목 */
export interface ServiceSyncStatusItem {
  entity_type: string;
  last_sync_status: SyncStatusValue | null;
  last_successful_sync_at: string | null;
  synced_entities: number;
  last_sync_error: string | null;
}

/** GET /api/v1/jira/sync/status?cloud_id= */
export interface JiraSyncStatusItem extends ServiceSyncStatusItem {
  cloud_id: string;
  project_key: string | null;
}

/** GET /api/v1/slack/sync/status?team_id= */
export interface SlackSyncStatusItem extends ServiceSyncStatusItem {
  team_id: string;
  oldest_ts: string | null;
  latest_ts: string | null;
}

/** GET /api/v1/confluence/sync/status?cloud_id= */
export interface ConfluenceSyncStatusItem extends ServiceSyncStatusItem {
  cloud_id: string;
  space_key: string;
  total_entities: number;
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
