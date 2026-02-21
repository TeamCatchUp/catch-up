export type { AuditAction, AuditLog, AuditStatus } from '@/shared/types/auditLog';

/** 감사 로그 테이블 행 렌더용 */
export interface AuditLogTableRow {
  key: string;
  name: string;
  picture: string | null;
  executedAt: string;
  action: string;
  status: string;
}

/** 정렬 키 */
export type AuditSortKey = 'newest' | 'oldest';
