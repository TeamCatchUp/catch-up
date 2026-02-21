import type { AuditAction, AuditSortKey, AuditStatus } from '../types/auditLog';

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
  성공: 'bg-green-10 text-green-60',
  실패: 'bg-neutral-2 text-gray-50',
};

/** 탭 목록 */
export const AUDIT_TABS = ['질문', '연동', '계정관리'] as const;
export type AuditTab = (typeof AUDIT_TABS)[number];
