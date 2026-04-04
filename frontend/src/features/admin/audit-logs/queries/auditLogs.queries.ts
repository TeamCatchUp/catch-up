import { queryOptions } from '@tanstack/react-query';

import type { AuditIntegrationLog } from '../types/auditIntegrationLogModel';
import type { AuditLog } from '../types/auditLogModel';
import type { AuditQuestionLog } from '../types/auditQuestionLogModel';

// TODO: 백엔드 API 준비 시 실제 API 호출로 교체
// Mock 버전: src/shared/mocks/admin/audit-logs/auditLogs.queries.ts

export const auditLogsQueries = {
  all: () => ['admin', 'auditLogs'] as const,

  list: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'list'] as const,
      queryFn: async (): Promise<AuditLog[]> => [],
    }),

  questions: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'questions'] as const,
      queryFn: async (): Promise<AuditQuestionLog[]> => [],
    }),

  integrations: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'integrations'] as const,
      queryFn: async (): Promise<AuditIntegrationLog[]> => [],
    }),
};
