import { QueryClient } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '@/test/msw/server';
import { API } from '@/shared/api/endpoints';

import { mcpScriptQueries } from './mcpScript.queries';
import { formatMcpInstallScriptValue } from '../utils/mcpScripts';

describe('mcpScriptQueries', () => {
  it('uses the shared MCP scripts endpoint', () => {
    expect(API.mcp.scripts).toBe('/api/v1/mcp/scripts');
    expect(mcpScriptQueries.scripts().queryKey).toEqual(['mypage', 'help', 'mcp-scripts']);
  });

  it('fetches install scripts and preserves string/object response values', async () => {
    const response = {
      mac: "curl -fsSL 'https://catchup.example/api/v1/mcp/scripts/mac' | bash",
      windows:
        "irm 'https://catchup.example/api/v1/mcp/scripts/windows' -OutFile (Join-Path $env:TEMP catchup_install.ps1)",
      claude_code: "claude mcp add --transport http catch-up 'https://catchup.example/api/v1/mcp/'",
      claude_desktop_config: {
        mcpServers: {
          'Catch Up': {
            command: 'npx',
            args: ['-y', 'mcp-remote', 'https://catchup.example/api/v1/mcp/', '--transport', 'http-only'],
          },
        },
      },
    };

    server.use(http.get('*/api/v1/mcp/scripts', () => HttpResponse.json(response)));

    const queryClient = new QueryClient();
    const data = await queryClient.fetchQuery(mcpScriptQueries.scripts());

    expect(data).toEqual(response);
    expect(formatMcpInstallScriptValue(data.claude_desktop_config)).toContain('"mcpServers"');
  });
});
