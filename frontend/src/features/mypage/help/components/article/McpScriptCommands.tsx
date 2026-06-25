'use client';

import { useQuery } from '@tanstack/react-query';

import { MCP_INSTALL_SCRIPT_ITEMS } from '../../constants/mcpScripts';
import { mcpScriptQueries } from '../../queries/mcpScript.queries';
import { formatMcpInstallScriptValue } from '../../utils/mcpScripts';
import HelpCommandBlock from './HelpCommandBlock';

type McpScriptKey = (typeof MCP_INSTALL_SCRIPT_ITEMS)[number]['key'];

interface McpScriptCommandsProps {
  scriptKeys?: readonly McpScriptKey[];
}

export default function McpScriptCommands({ scriptKeys }: McpScriptCommandsProps) {
  const { data, isError, isLoading } = useQuery(mcpScriptQueries.scripts());
  const scriptItems = scriptKeys
    ? MCP_INSTALL_SCRIPT_ITEMS.filter((item) => scriptKeys.includes(item.key))
    : MCP_INSTALL_SCRIPT_ITEMS;

  return (
    <div className="flex flex-col gap-6">
      {scriptItems.map((item) => (
        <div key={item.key} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <h3 className="text-reading-heading-sb-medium text-text-normal-strong">{item.label}</h3>
            <p className="text-reading-body-md-small text-text-normal-alternative">{item.description}</p>
          </div>
          <HelpCommandBlock
            value={data ? formatMcpInstallScriptValue(data[item.key]) : undefined}
            ariaLabel={`${item.label} 복사`}
            isLoading={isLoading}
            isError={isError}
          />
        </div>
      ))}
    </div>
  );
}
