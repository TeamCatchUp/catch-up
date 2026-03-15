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
  identifier: string | null; // email 또는 github login
  picture: string | null;
}

export interface UserSyncItem {
  sub: string;
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

// ─── Vendor Users (툴별 사용자 목록 드롭다운) ───

export interface ToolUserResponse {
  id: string;
  name: string;
  identifier: string | null; // email 또는 github login
  picture: string | null;
}

export interface VendorUsersResponse {
  total: number;
  page: number;
  size: number;
  items: ToolUserResponse[];
}

// ─── Pre-mapping Bulk Update ───

export interface PreMappingUpdateItem {
  sub: string;
  email: string;
  name: string;
  is_ignored: boolean;
  external_user_identifier: string | null;
}

export interface PreMappingBulkUpdateResponse {
  message: string;
  processed_count: number;
}
