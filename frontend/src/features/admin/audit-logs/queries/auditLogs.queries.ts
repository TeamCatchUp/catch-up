import { queryOptions } from '@tanstack/react-query';

// TODO: 백엔드 API 준비 시 실제 API 호출로 교체
// Mock 버전: src/shared/mocks/admin/audit-logs/auditLogs.queries.ts

export const auditLogsQueries = {
  all: () => ['admin', 'auditLogs'] as const,

  list: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'list'] as const,
      queryFn: async () => [],
    }),

  questions: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'questions'] as const,
      queryFn: async () => [],
    }),

  integrations: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'integrations'] as const,
      queryFn: async () => [],
    }),
};
