import type { IntegrationService } from '@/shared/types/integrationService';

/** 감사 로그 액션 종류 */
export type AuditAction = 'join' | 'login' | 'logout' | 'deactivate' | 'withdraw';

/** 감사 로그 상태 */
export type AuditStatus = 'success' | 'failure';

/** 감사 로그 엔트리 */
export interface AuditLog {
  logId: string;
  userId: string;
  name: string;
  email: string;
  picture: string | null;
  department: string;
  rank: string;
  joinedAt: string;
  approver: string;
  action: AuditAction;
  status: AuditStatus;
  executedAt: string;
  accountIds: Partial<Record<IntegrationService, string>>;
}
