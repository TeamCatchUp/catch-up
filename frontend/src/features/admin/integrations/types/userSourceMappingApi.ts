/** Backend StrEnum mirror — drives ?mapping_status= query param. */
export type UserSourceMappingStatus = 'all' | 'full' | 'partial';

export interface MappedSourceInfo {
  name: string | null;
  identifier: string | null;
  picture: string | null;
}

/**
 * 백엔드 PR #610 ITEM_FIELD_BY_SOURCE에서 Confluence 매핑은 atlassian 필드로 합쳐서 응답.
 * `confluence` 키는 스키마에 존재하지만 실제 응답에서는 항상 null.
 */
export interface UserSourceMappingItem {
  user_id: number;
  sub: string | null;
  name: string;
  email: string;
  atlassian: MappedSourceInfo | null;
  slack: MappedSourceInfo | null;
  github: MappedSourceInfo | null;
  confluence: MappedSourceInfo | null;
  channel_talk: MappedSourceInfo | null;
}

export interface UserSourceMappingResponse {
  total: number;
  page: number;
  size: number;
  items: UserSourceMappingItem[];
}

export interface MappingStatusCount {
  users: number;
  mapped: number;
}

export interface MappingStatusResponse {
  jira: MappingStatusCount;
  slack: MappingStatusCount;
  github: MappingStatusCount;
  confluence: MappingStatusCount;
  channel_talk: MappingStatusCount;
}

export interface UserSourceMappingRefreshResponse {
  scanned_users: number;
  inserted: Record<string, number>;
  skipped_existing: Record<string, number>;
  not_found: Record<string, number>;
}
