import type { IntegrationService } from '@/shared/types/integrationService';

/** 연동 로그 구분 */
export type IntegrationLogCategory = 'sync' | 'api_call' | 'integration';

/** 연동 감사 로그 엔트리 */
export interface AuditIntegrationLog {
  logId: string;
  service: IntegrationService;
  executedAt: string;
  category: IntegrationLogCategory;
  userId: number;
  userName: string;
  userPicture: string | null;
  status: 'success' | 'failure';
  /** 동기화/연동 전용 — 연동된 데이터 범위 */
  dataRange?: string;
  /** 동기화/연동 전용 — 리소스 이름 목록 */
  resources?: string[];
  /** API 호출 전용 — 호출 사유 */
  apiCallReason?: string;
  /** API 호출 전용 — 수신 데이터 (JSON 등) */
  receivedData?: string;
}
