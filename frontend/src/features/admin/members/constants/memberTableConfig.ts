/** 직급 Badge 스타일 */
export const RANK_BADGE_CLASS: Record<string, string> = {
  팀장: 'bg-violet-5 text-violet-60',
  과장: 'bg-orange-5 text-orange-60',
  대리: 'bg-green-5 text-green-60',
  사원: 'bg-blue-5 text-blue-50',
};

/** 권한 → 한글 라벨 */
export const ROLE_LABEL: Record<string, string> = {
  admin: '관리자',
  user: 'Member',
};

/** 권한 Badge 스타일 */
export const ROLE_BADGE_CLASS: Record<string, string> = {
  관리자: 'bg-blue-5 text-blue-50',
  Member: 'bg-neutral-2 text-gray-50',
};

/** 부서 Badge 스타일 */
export const DEPT_BADGE_CLASS = 'bg-green-5 text-green-60';

/** Tag 공통 스타일 */
export const TAG_BASE_CLASS = 'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center px-1.5 py-0.5 truncate';
