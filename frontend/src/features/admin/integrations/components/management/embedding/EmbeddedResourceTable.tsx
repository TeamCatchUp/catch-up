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
 * 범위 열은 폭을 박지 않는다. `whitespace-nowrap`이면 브라우저가 내용 폭(=180)을
 * 그대로 주고, 대상 열이 `w-full max-w-0`으로 나머지를 먹은 뒤 truncate된다.
 * 192를 고정하면 좁은 슬롯에서 대상 열이 먼저 무너져 가로 스크롤이 필요해진다.
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
    <table className="w-full">
      <thead>
        <tr className="h-9">
          {/* truncate: 좁은 슬롯에서 라벨이 두 줄로 접혀 헤더가 36을 넘는 걸 막는다 */}
          <th
            scope="col"
            className="text-body-xsmall text-text-normal-alternative w-full truncate pr-4 pl-3 text-left font-medium"
          >
            {label}
          </th>
          <th
            scope="col"
            className="text-body-xsmall text-text-normal-alternative pr-3 text-left font-medium whitespace-nowrap"
          >
            데이터 범위
          </th>
        </tr>
      </thead>

      {rows.map((row, groupIndex) => (
        <tbody key={row.id}>
          <tr className={groupIndex > 0 ? 'h-12 border-t-2 border-transparent' : 'h-11.5'}>
            {/* max-w-0 + w-full: 나머지 폭을 다 먹으면서 truncate가 걸리게 하는 표 전용 관용구 */}
            <td className="w-full max-w-0 py-2 pr-4 pl-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <Logo className="size-5 shrink-0" />
                <span className="text-body-small text-text-normal-neutral truncate">{row.name}</span>
              </div>
            </td>
            <td className="text-body-small text-text-normal-assistive py-2 pr-3 whitespace-nowrap">{row.dataRange}</td>
          </tr>

          {row.children?.map((child) => (
            <tr key={child.id} className="h-11.5">
              <td className="w-full max-w-0 pr-4 pl-5.5">
                <div className="flex min-w-0 items-center gap-2.5">
                  <IconConnector aria-hidden="true" className="h-11.75 w-3.5 shrink-0" />
                  <span className="text-body-small text-text-normal-neutral truncate">{child.name}</span>
                </div>
              </td>
              <td className="text-body-small text-text-normal-assistive pr-3 whitespace-nowrap">{child.dataRange}</td>
            </tr>
          ))}
        </tbody>
      ))}
    </table>
  );
}
