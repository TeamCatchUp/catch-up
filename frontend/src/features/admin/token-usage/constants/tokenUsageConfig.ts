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
export const fromTabSlug = (slug: string): TokenUsageTab => SLUG_TO_TAB[slug as TokenUsageTabSlug] ?? '나의 토큰 사용량';

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
