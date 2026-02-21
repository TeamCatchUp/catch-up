import { queryOptions } from '@tanstack/react-query';

import { MOCK_AUDIT_LOGS } from '../mocks/auditLogsMockData';

export const auditLogsQueries = {
  all: () => ['admin', 'auditLogs'] as const,

  list: () =>
    queryOptions({
      queryKey: [...auditLogsQueries.all(), 'list'] as const,
      queryFn: async () => MOCK_AUDIT_LOGS,
    }),
};
