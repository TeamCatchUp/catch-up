import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { McpInstallScriptsResponse } from '../types/mcpScripts';

export const mcpScriptQueries = {
  all: () => ['mypage', 'help', 'mcp-scripts'] as const,

  scripts: () =>
    queryOptions({
      queryKey: mcpScriptQueries.all(),
      queryFn: async (): Promise<McpInstallScriptsResponse> => {
        const res = await api.get<McpInstallScriptsResponse>(API.mcp.scripts);
        return res.data;
      },
    }),
};
