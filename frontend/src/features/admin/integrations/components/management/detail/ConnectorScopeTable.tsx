import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';

interface ConnectorScopeTableProps {
  service: IntegrationService;
}

/**
 * "연동 범위" 4행 표.
 * Figma `16922:134113` — 행 padding 14/20, gap 16, 라벨 열 150px 고정,
 * 마지막 행을 뺀 나머지에 하단 경계선.
 */
export default function ConnectorScopeTable({ service }: ConnectorScopeTableProps) {
  const { scope } = CONNECTOR_CONTENT[service];

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-heading-small text-text-normal-normal">연동 범위</h3>
      <table className="border-line-normal-neutral w-full table-fixed overflow-hidden rounded-xl border">
        <tbody>
          {scope.map((row, index) => (
            <tr key={row.label} className={index < scope.length - 1 ? 'border-line-normal-neutral border-b' : undefined}>
              <th
                scope="row"
                className="text-body-small text-text-normal-alternative w-37.5 px-5 py-3.5 text-left font-medium"
              >
                {row.label}
              </th>
              <td className="text-body-small text-text-normal-normal px-5 py-3.5">{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
