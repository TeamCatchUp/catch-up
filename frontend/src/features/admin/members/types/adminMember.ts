import type { UserRole, UserStatus } from '@/shared/queries/auth.types';
import type { IntegrationService } from '@/shared/types/integrationService';

/** 입장 신청 목록 행 */
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

/** 이용자 목록 행 */
export interface AdminMember {
  userId: string;
  name: string;
  email: string;
  phone: string;
  picture: string | null;
  department: string;
  teamSize: number;
  rank: string;
  role: UserRole;
  status: UserStatus;
  accountIds: Partial<Record<IntegrationService, string>>;
}

/** 승인/반려 요청 body */
export interface RequestDecisionPayload {
  requestIds: string[];
  decision: 'approve' | 'reject';
}

/** 이용자 상태 변경 body */
export interface MemberStatusPayload {
  userId: string;
  action: 'deactivate' | 'delete';
}

/** 이용자 테이블 정렬 키 */
export type AdminSortKey = 'newest' | 'oldest';

/** 테이블 행 렌더용 공통 인터페이스 */
export interface MemberTableRow {
  key: string;
  name: string;
  picture: string | null;
  rank: string;
  department: string;
  /** 4번째 컬럼 값 (상태 or 권한) */
  lastColumn: string;
}
