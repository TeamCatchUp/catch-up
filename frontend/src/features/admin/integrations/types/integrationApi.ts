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
