import type { UserRole, UserStatus } from '@/shared/queries/auth.types';
import type { IntegrationService } from '@/shared/types/integrationService';

// ─── JobLevel ───

export type JobLevel = 'executive' | 'leader' | 'member';

// ─── 목록 (GET /admin/users) ───

export interface AdminUserListItem {
  id: number;
  name: string;
  department: string;
  jobLevel: JobLevel;
  role: UserRole;
  status: UserStatus;
}

export interface AdminUserListResponse {
  total: number;
  users: AdminUserListItem[];
}

// ─── 상세 (GET /admin/users/{id}) ───

interface IntegrationAccountBase {
  name?: string | null;
  email?: string | null;
  avatarUrl?: string | null;
}

export interface JiraAccount extends IntegrationAccountBase {
  accountId: string;
}

export interface GithubAccount extends IntegrationAccountBase {
  login: string;
}

export interface SlackAccount extends IntegrationAccountBase {
  userId: string;
}

export interface ConfluenceAccount extends IntegrationAccountBase {
  accountId: string;
}

export interface UserIntegrations {
  jira: JiraAccount | null;
  github: GithubAccount | null;
  slack: SlackAccount | null;
  confluence: ConfluenceAccount | null;
  /** 채널톡은 organization-level 연동이라 user-level account가 없음 (항상 null) */
  'channel-talk': null;
}

export interface AdminUserDetailResponse {
  id: number;
  name: string;
  email: string;
  picture: string | null;
  department: string;
  jobLevel: JobLevel;
  status: UserStatus;
  integrations: UserIntegrations;
}

// ─── 입장 신청 (기존 유지) ───

export interface EntryRequest {
  requestId: string;
  userId: string;
  name: string;
  email: string;
  phone: string;
  picture: string | null;
  department: string;
  teamSize: number;
  rank: string;
  role: UserRole;
  requestedAt: string;
  accountIds: Partial<Record<IntegrationService, string>>;
}

export interface RequestDecisionPayload {
  requestIds: string[];
  decision: 'approve' | 'reject';
}

// ─── 테이블 공통 ───

export type AdminSortKey = 'newest' | 'oldest';

export interface MemberTableRow {
  key: string;
  name: string;
  picture: string | null;
  rank: string;
  department: string;
  lastColumn: string;
}
