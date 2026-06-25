export type McpInstallScriptValue = string | Record<string, unknown>;

export interface McpInstallScriptsResponse {
  mac: string;
  windows: string;
  claude_code: string;
  claude_desktop_config: Record<string, unknown>;
}

export type McpInstallScriptKey = keyof McpInstallScriptsResponse;

export interface McpInstallScriptDisplayItem {
  key: McpInstallScriptKey;
  label: string;
  description: string;
}
