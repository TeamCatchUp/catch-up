import type { IntegrationService } from '@/shared/types/integrationService';

import type { IntegrationLogCategory } from '../types/auditIntegrationLogModel';
import type { AuditAction, AuditSortKey, AuditStatus } from '../types/auditLogModel';

/** 정렬 옵션 */
export const SORT_OPTIONS: { key: AuditSortKey; label: string }[] = [
  { key: 'newest', label: '최신 순' },
  { key: 'oldest', label: '오래된 순' },
];

/** 액션 → 한글 라벨 */
export const ACTION_LABEL: Record<AuditAction, string> = {
  join: '가입',
  login: '로그인',
  logout: '로그아웃',
  deactivate: '비활성화',
  withdraw: '탈퇴',
};

/** 상태 → 한글 라벨 */
export const STATUS_LABEL: Record<AuditStatus, string> = {
  success: '성공',
  failure: '실패',
};

/** 상태 배지 스타일 */
export const STATUS_BADGE_CLASS: Record<string, string> = {
  성공: 'bg-accent-green-neutral text-accent-green',
  실패: 'bg-neutral-2 text-content-alternative',
};

/** 연동 로그 구분 라벨 */
export const CATEGORY_LABEL: Record<IntegrationLogCategory, string> = {
  sync: '동기화',
  api_call: 'API 호출',
  integration: '연동',
};

/** 서비스별 리소스 섹션 라벨 */
export const RESOURCE_LABEL: Record<IntegrationService, string> = {
  jira: '연동된 Jira Space',
  github: '연동된 Repository',
  slack: '연동된 채널',
  confluence: '연동된 스페이스',
  'channel-talk': '연동된 채널톡 채널',
};

/** 탭 목록 */
export const AUDIT_TABS = ['질문', '연동', '계정관리'] as const;
export type AuditTab = (typeof AUDIT_TABS)[number];

/** 탭 ↔ URL slug 매핑 */
export type AuditTabSlug = 'question' | 'integration' | 'account';

const TAB_TO_SLUG: Record<AuditTab, AuditTabSlug> = {
  질문: 'question',
  연동: 'integration',
  계정관리: 'account',
};

const SLUG_TO_TAB: Record<AuditTabSlug, AuditTab> = {
  question: '질문',
  integration: '연동',
  account: '계정관리',
};

export const DEFAULT_TAB_SLUG: AuditTabSlug = 'question';

export const toTabSlug = (tab: AuditTab): AuditTabSlug => TAB_TO_SLUG[tab];
export const fromTabSlug = (slug: string): AuditTab => SLUG_TO_TAB[slug as AuditTabSlug] ?? '질문';
