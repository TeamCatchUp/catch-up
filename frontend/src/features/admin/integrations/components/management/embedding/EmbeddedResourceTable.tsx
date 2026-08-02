import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';
import EmbeddingEmptyState from '../states/EmbeddingEmptyState';

export interface EmbeddedResourceRow {
  id: string;
  name: string;
  dataRange: string;
}

interface EmbeddedResourceTableProps {
  service: IntegrationService;
  /** 도구마다 다른 첫 열 라벨. 예: "임베딩된 채널" / "임베딩된 스페이스" */
  label: string;
  rows: readonly EmbeddedResourceRow[];
}

/**
 * 임베딩 관리 탭의 대상 목록.
 * Figma `17071:111748` — 헤더 716×36, 행 716×46, 대상 x12 w496, 범위 x524 w180.
 *
 * 비면 표 대신 빈 상태로 통째로 교체된다(요약 카드는 위에 그대로 남는다).
 * Figma는 9행 고정에 페이지네이션이 없다 — 현행 Pagination 유지 여부는 계획 ④에서 정한다.
 */
export default function EmbeddedResourceTable({ service, label, rows }: EmbeddedResourceTableProps) {
  const Logo = CONNECTOR_LOGOS[service];

  if (rows.length === 0) return <EmbeddingEmptyState />;

  return (
    <table className="w-full table-fixed">
      <thead>
        <tr className="h-9">
          <th scope="col" className="text-body-xsmall text-text-normal-alternative pr-4 pl-3 text-left font-medium">
            {label}
          </th>
          <th scope="col" className="text-body-xsmall text-text-normal-alternative w-45 pr-3 text-left font-medium">
            데이터 범위
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} className="h-11.5">
            <td className="py-2 pr-4 pl-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <Logo className="size-5 shrink-0" />
                <span className="text-body-small text-text-normal-neutral truncate">{row.name}</span>
              </div>
            </td>
            <td className="text-body-small text-text-normal-assistive w-45 py-2 pr-3">{row.dataRange}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
