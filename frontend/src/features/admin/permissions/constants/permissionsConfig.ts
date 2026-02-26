import {
  JOB_LEVEL_LABEL as MEMBER_JOB_LEVEL_LABEL,
  RANK_BADGE_CLASS as MEMBER_RANK_BADGE_CLASS,
  TAG_BASE_CLASS as MEMBER_TAG_BASE_CLASS,
} from '@/features/admin/members/constants/memberTableConfig';

import type { PermissionRole } from '../types/adminPermission';

export const LIST_PAGE_SIZE = 15;

export const ADMIN_OWNER_LABEL = 'Admin 권한 소유자';
export const ADMIN_OWNER_LINE_1 = '현재 Admin 권한 소유자 : 직원01(CTO)';
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
  Admin: 'bg-blue-5 text-blue-50',
  Member: 'bg-neutral-2 text-gray-50',
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
