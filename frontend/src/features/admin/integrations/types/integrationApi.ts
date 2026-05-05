// ─── Vendor Type ───

export type VendorType = 'github' | 'slack' | 'atlassian' | 'channel_talk';

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

// ─── User Mapping Filter Chip (frontend-only state) ───

/**
 * 이용자 연동 탭 필터 칩 상태.
 * `'all' | 'full' | 'partial'` → backend `?mapping_status=`로 그대로 매핑.
 * `'channel_talk'` → backend는 `mapping_status='all'`로 호출하고 frontend가 컬럼만 좁힘.
 */
export type SyncFilterType = 'all' | 'full' | 'partial' | 'channel_talk';

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
