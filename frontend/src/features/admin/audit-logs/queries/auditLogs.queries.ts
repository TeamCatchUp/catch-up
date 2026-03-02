import { queryOptions } from '@tanstack/react-query';

import { MOCK_AUDIT_INTEGRATION_LOGS } from '@/shared/mocks/admin/audit-logs/auditIntegrationMockData';
import { MOCK_AUDIT_LOGS } from '@/shared/mocks/admin/audit-logs/auditLogsMockData';
import { MOCK_AUDIT_QUESTION_LOGS } from '@/shared/mocks/admin/audit-logs/auditQuestionMockData';

export const auditLogsQueries = {
  all: () => ['admin', 'auditLogs'] as const,

  list: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'list'] as const,
      queryFn: async () => MOCK_AUDIT_LOGS,
    }),

  questions: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'questions'] as const,
      queryFn: async () => MOCK_AUDIT_QUESTION_LOGS,
    }),

  integrations: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'integrations'] as const,
      queryFn: async () => MOCK_AUDIT_INTEGRATION_LOGS,
    }),
};
