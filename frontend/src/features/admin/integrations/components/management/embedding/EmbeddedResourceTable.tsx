import IconConnector from '@/public/icons/icon/connector.svg';

import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';
import EmbeddingEmptyState from '../states/EmbeddingEmptyState';

export interface EmbeddedResourceRow {
  id: string;
  name: string;
  dataRange: string;
  /**
   * 채널톡 전용 — 채널 하위 도큐먼트 스페이스.
   * 다른 도구는 계층이 없어 비워 둔다.
   */
  children?: readonly EmbeddedResourceRow[];
}

interface EmbeddedResourceTableProps {
  service: IntegrationService;
  /** 도구마다 다른 첫 열 라벨. 예: "임베딩된 채널" / "임베딩된 스페이스" */
  label: string;
  rows: readonly EmbeddedResourceRow[];
}

/**
 * 임베딩 관리 탭의 대상 목록.
 * Figma `17071:111748`(Slack) · `17169:31054`(Jira) · `17169:75856`(채널톡).
 *
 * 표 716, 헤더 36, 행 46. 대상 x12 w496 / 범위 x524 w180.
 * 범위 열은 `716-524=192`이고 그 안에서 내용이 180을 정확히 채운다
 * (`2000.00.00`81 + 6 + `-`7 + 6 + `2000.00.00`80). 192보다 좁히면 줄바꿈이 난다.
 *
 * 채널톡만 채널 → 도큐먼트 스페이스 2단 계층이다. 도큐먼트 행은 x22로 들여쓰고
 * 로고 대신 `icon/connector`(15×47 세로선 + 가운데 가지)를 놓는다. 행 높이 46보다
 * 1px 큰 아이콘이라 연속된 도큐먼트의 선이 이어져 보인다.
 * 채널 묶음 사이는 2px 띄운다.
 */
export default function EmbeddedResourceTable({ service, label, rows }: EmbeddedResourceTableProps) {
  const Logo = CONNECTOR_LOGOS[service];

  if (rows.length === 0) return <EmbeddingEmptyState />;

  return (
    // 범위 열이 192로 고정이라 좁아지면 대상 열이 짓눌린다. 최소 폭을 두고 넘치면 가로 스크롤
    <div className="overflow-x-auto">
      <table className="w-full min-w-100 table-fixed">
        <thead>
          <tr className="h-9">
            <th scope="col" className="text-body-xsmall text-text-normal-alternative pr-4 pl-3 text-left font-medium">
              {label}
            </th>
            <th scope="col" className="text-body-xsmall text-text-normal-alternative w-48 pr-3 text-left font-medium">
              데이터 범위
            </th>
          </tr>
        </thead>

        {rows.map((row, groupIndex) => (
          <tbody key={row.id}>
            <tr className={groupIndex > 0 ? 'h-12 border-t-2 border-transparent' : 'h-11.5'}>
              <td className="py-2 pr-4 pl-3">
                <div className="flex min-w-0 items-center gap-2.5">
                  <Logo className="size-5 shrink-0" />
                  <span className="text-body-small text-text-normal-neutral truncate">{row.name}</span>
                </div>
              </td>
              <td className="text-body-small text-text-normal-assistive w-48 py-2 pr-3 whitespace-nowrap">
                {row.dataRange}
              </td>
            </tr>

            {row.children?.map((child) => (
              <tr key={child.id} className="h-11.5">
                <td className="pr-4 pl-5.5">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <IconConnector aria-hidden="true" className="h-11.75 w-3.5 shrink-0" />
                    <span className="text-body-small text-text-normal-neutral truncate">{child.name}</span>
                  </div>
                </td>
                <td className="text-body-small text-text-normal-assistive w-48 pr-3 whitespace-nowrap">
                  {child.dataRange}
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
