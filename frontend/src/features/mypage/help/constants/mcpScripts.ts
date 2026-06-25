import type { McpInstallScriptDisplayItem } from '../types/mcpScripts';

export const MCP_INSTALL_SCRIPT_ITEMS = [
  {
    key: 'mac',
    label: 'Mac',
    description: '터미널에서 실행할 Claude Desktop 설치 명령어입니다.',
  },
  {
    key: 'windows',
    label: 'Windows',
    description: 'PowerShell에서 실행할 Claude Desktop 설치 명령어입니다.',
  },
  {
    key: 'claude_code',
    label: 'Claude Code',
    description: 'Claude Code CLI에 Catch Up MCP 서버를 등록합니다.',
  },
  {
    key: 'claude_desktop_config',
    label: 'Claude Desktop 설정',
    description: '자동 설치 대신 설정 파일에 직접 넣을 때 사용하는 값입니다.',
  },
] satisfies readonly McpInstallScriptDisplayItem[];
