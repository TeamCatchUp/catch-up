import type { McpInstallScriptValue } from '../types/mcpScripts';

export function formatMcpInstallScriptValue(value: McpInstallScriptValue): string {
  if (typeof value === 'string') {
    return value;
  }

  return JSON.stringify(value, null, 2);
}
