import type { UserStatus } from '@/shared/queries/auth.types';

import type { AdminSortKey, JobLevel } from '../types/adminMember';

/** 정렬 옵션 */
export const SORT_OPTIONS: { key: AdminSortKey; label: string }[] = [
  { key: 'newest', label: '최신 순' },
  { key: 'oldest', label: '오래된 순' },
];

/** jobLevel → 한글 라벨 */
export const JOB_LEVEL_LABEL: Record<JobLevel, string> = {
  executive: '경영진',
  leader: '팀장',
  member: '팀원',
};

/** 직급 Badge 스타일 */
export const RANK_BADGE_CLASS: Record<string, string> = {
  경영진: 'bg-accent-red-orange-neutral text-accent-red-orange',
  팀장: 'bg-accent-violet-lighten text-accent-violet',
  팀원: 'bg-blue-5 text-content-primary',
};

/** 권한 → 한글 라벨 */
export const ROLE_LABEL: Record<string, string> = {
  admin: '관리자',
  user: 'Member',
};

/** 권한 Badge 스타일 */
export const ROLE_BADGE_CLASS: Record<string, string> = {
  관리자: 'bg-blue-5 text-content-primary',
  Member: 'bg-fill-interaction-hover text-content-alternative',
};

/** 상태 → 한글 라벨 */
export const STATUS_LABEL: Partial<Record<UserStatus, string>> = {
  active: '이용중',
  inactive: '비활성화',
};

/** 상태 Badge 스타일 */
export const STATUS_BADGE_CLASS: Record<string, string> = {
  이용중: 'bg-accent-green-neutral text-accent-green',
  비활성화: 'bg-fill-interaction-hover text-content-alternative',
};

/** Tag 공통 스타일 */
export const TAG_BASE_CLASS = 'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center px-1.5 py-0.5 truncate';

/** 반려 사유 */
export const REJECTION_REASONS = [
  '업무 연관성 부족',
  '보안 및 민감 정보 포함',
  '프로젝트 상태 종료 또는 접근 불필요',
  '요청 사유 불충분',
  '사내 정책 미충족',
  '직접 입력',
] as const;

/** 비활성화 사유 */
export const DEACTIVATION_REASONS = [
  '협업 툴 계정 정보 불일치',
  '보안 및 민감 정보 조회 시도',
  '사내 정보 접근 불필요',
  '사내 정책 미충족',
  '직접 입력',
] as const;
