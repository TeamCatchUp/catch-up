import type { TokenUsageSummary } from '../types/tokenUsage';

/** 탭 목록 */
export const TOKEN_USAGE_TABS = ['나의 토큰 사용량', '조직 토큰 사용량', '이용자 관리', '제한 해제 요청'] as const;
export type TokenUsageTab = (typeof TOKEN_USAGE_TABS)[number];

/** 탭 ↔ URL slug 매핑 */
export type TokenUsageTabSlug = 'my-usage' | 'org-usage' | 'user-management' | 'limit-release';

const TAB_TO_SLUG: Record<TokenUsageTab, TokenUsageTabSlug> = {
  '나의 토큰 사용량': 'my-usage',
  '조직 토큰 사용량': 'org-usage',
  '이용자 관리': 'user-management',
  '제한 해제 요청': 'limit-release',
};

const SLUG_TO_TAB: Record<TokenUsageTabSlug, TokenUsageTab> = {
  'my-usage': '나의 토큰 사용량',
  'org-usage': '조직 토큰 사용량',
  'user-management': '이용자 관리',
  'limit-release': '제한 해제 요청',
};

export const DEFAULT_TAB_SLUG: TokenUsageTabSlug = 'my-usage';

export const toTabSlug = (tab: TokenUsageTab): TokenUsageTabSlug => TAB_TO_SLUG[tab];
export const fromTabSlug = (slug: string): TokenUsageTab =>
  SLUG_TO_TAB[slug as TokenUsageTabSlug] ?? '나의 토큰 사용량';

/** 상태 Badge 매핑 */
export const STATUS_CONFIG: Record<
  TokenUsageSummary['status'],
  { label: string; variant: 'success' | 'orange' | 'red' }
> = {
  normal: { label: '정상', variant: 'success' },
  warning: { label: '주의', variant: 'orange' },
  exceeded: { label: '초과', variant: 'red' },
};

/** 설정 기본값 (프론트 고정) */
export const DEFAULT_DAILY_LIMIT = 5;
export const DEFAULT_MONTHLY_LIMIT = 100;

/** ── 이용자 관리 ── */

export type UserMgmtSortKey = 'newest' | 'name' | 'cost';
export const USER_MGMT_SORT_OPTIONS: { key: UserMgmtSortKey; label: string }[] = [
  { key: 'newest', label: '최신 순' },
  { key: 'name', label: '이름 순' },
  { key: 'cost', label: '사용량 순' },
];

/** 직급 Badge 색상 (members RANK_BADGE_CLASS 동일) */
export const POSITION_BADGE_CLASS: Record<string, string> = {
  경영진: 'bg-accent-red-orange-neutral text-accent-red-orange',
  팀장: 'bg-accent-violet-lighten text-accent-violet',
  팀원: 'bg-fill-primary-normal-neutral text-content-primary',
};

/** 부서 Badge 색상 */
export const TEAM_BADGE_CLASS = 'bg-accent-green-neutral text-accent-green';

/** 페이지당 행 수 */
export const USERS_PER_PAGE = 10;
