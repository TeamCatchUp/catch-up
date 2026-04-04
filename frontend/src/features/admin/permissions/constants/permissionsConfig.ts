import {
  JOB_LEVEL_LABEL as MEMBER_JOB_LEVEL_LABEL,
  RANK_BADGE_CLASS as MEMBER_RANK_BADGE_CLASS,
  TAG_BASE_CLASS as MEMBER_TAG_BASE_CLASS,
} from '@/features/admin/members/constants/memberTableConfig';

import type { PermissionRole } from '../types/adminPermissionModel';

export const LIST_PAGE_SIZE = 15;

export const ADMIN_OWNER_LABEL = 'Admin 권한';
export const ADMIN_OWNER_LINE_1 = '';
export const ADMIN_OWNER_LINE_2 =
  'Admin 주요 기능 : 워크스페이스 설정, 멤버 관리 및 권한 제어를 포함한 모든 관리 도구에 접근할 수 있습니다.';

export const JOB_LEVEL_LABEL = MEMBER_JOB_LEVEL_LABEL;
export const RANK_BADGE_CLASS = MEMBER_RANK_BADGE_CLASS;
export const TAG_BASE_CLASS = MEMBER_TAG_BASE_CLASS;

export const ROLE_LABEL: Record<PermissionRole, 'Admin' | 'Member'> = {
  admin: 'Admin',
  user: 'Member',
};

export const ROLE_BADGE_CLASS: Record<'Admin' | 'Member', string> = {
  Admin: 'bg-fill-primary-normal-neutral text-content-primary',
  Member: 'bg-fill-interaction-hover text-content-alternative',
};

export const ROLE_FILTER_OPTIONS = [
  { key: 'all', label: '전체' },
  { key: 'admin', label: 'Admin' },
  { key: 'user', label: 'Member' },
] as const;

export type RoleFilter = (typeof ROLE_FILTER_OPTIONS)[number]['key'];

export const PERMISSION_CHANGE_REASONS = [
  '담당자 변경 (퇴사/이동/인수인계)',
  '운영 분산',
  '보안/감사 대응',
  '일시적 승격',
  '직접 입력',
] as const;

/** promote API 에러 코드 → 사용자 메시지 */
export const PROMOTE_ERROR_MESSAGES: Record<string, string> = {
  user_not_found: '해당 사용자를 찾을 수 없습니다.',
  user_already_admin: '이미 Admin 권한을 보유한 사용자입니다.',
  cannot_promote_deleted_user: '삭제된 사용자에게 권한을 부여할 수 없습니다.',
  cannot_promote_inactive_user: '비활성화된 사용자에게 권한을 부여할 수 없습니다.',
};

/** revoke API 에러 코드 → 사용자 메시지 */
export const REVOKE_ERROR_MESSAGES: Record<string, string> = {
  user_not_found: '해당 사용자를 찾을 수 없습니다.',
  user_already_user: '이미 일반 사용자입니다.',
  cannot_revoke_own_admin_role: '자신의 Admin 권한은 회수할 수 없습니다.',
  cannot_revoke_deleted_user: '삭제된 사용자의 권한을 회수할 수 없습니다.',
  cannot_revoke_inactive_user: '비활성화된 사용자의 권한을 회수할 수 없습니다.',
  admin_count_violation: 'Admin이 1명뿐이므로 권한을 회수할 수 없습니다.',
};

/** 권한 조정 사유 (Figma 디자인 기준) */
export const PERMISSION_ROLE_CHANGE_REASONS = [
  '업무 변경',
  '역할 변경',
  '부서 이동',
  '휴직 / 퇴직',
  '직접 입력',
] as const;
