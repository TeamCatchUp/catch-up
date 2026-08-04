import IconConnector from '@/public/icons/icon/connector.svg';
import IconConnectorLast from '@/public/icons/icon/connector_last.svg';
import { cn } from '@/shared/utils/cn';

import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';
import EmbeddingEmptyState from '../states/EmbeddingEmptyState';
import { RESOURCE_ROW_GRID } from './embeddingTableGrid';

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

/**
 * 마지막 도큐먼트의 `icon/connector_last` 를 `icon/connector` 와 같은 좌표계에 올린다.
 *
 * 두 에셋은 같은 자리에 놓이도록 그려졌지만 내보내기 박스가 다르다 —
 * `connector_last` 는 15×21로 잘려 나왔고, 세로선은 그 위(y=-3.5)부터 그려져 있다.
 * 잘린 채로 두면 위 도큐먼트의 선과 2.5px 벌어진다. 뷰박스를 -3.5부터 47까지로
 * 되돌리면 세로선 시작점과 꺾이는 지점(y=20.5 → 박스 기준 24)이 `connector`(y=24.01)와
 * 겹쳐, 가지 아래로 이어지던 선만 사라진다.
 *
 * 박스도 뷰박스와 같은 15×47(`w-3.75 h-11.75`)이어야 한다. 어긋나면 preserveAspectRatio가
 * 축소를 걸어(14/15) 꺾이는 지점이 위로 밀린다. svgr이 뷰박스를 지우고 내보내는 탓에
 * `connector` 쪽은 축소 없이 1:1로 그려지고 있어서, 이쪽만 줄어들면 둘이 어긋난다.
 *
 * 에셋을 다시 내보내 crop 이 바뀌면 이 값도 같이 고쳐야 한다.
 */
const LAST_CONNECTOR_VIEW_BOX = '0 -3.5 15 47';

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
 * 표 716, 헤더 36, 행 46. 실측 행 `17169:75787`:
 * `716 = 12 | 대상(fill) 496 | 16 | 범위(hug) 180 | 12`.
 * 열 폭은 {@link RESOURCE_ROW_GRID}가 정한다 — 범위는 `auto`+nowrap이라
 * 내용 폭을 그대로 갖고, 대상이 남은 폭을 먹은 뒤 truncate된다.
 *
 * 채널톡만 채널 → 도큐먼트 스페이스 2단 계층이다. 도큐먼트 행은 x22로 들여쓰고
 * 로고 대신 `icon/connector`(15×47 세로선 + 가운데 가지)를 놓는다. 행 높이 46보다
 * 1px 큰 아이콘이라 연속된 도큐먼트의 선이 이어져 보인다. 마지막 도큐먼트만
 * 가지 아래로 선이 남지 않는 `icon/connector_last`를 쓴다 —
 * {@link LAST_CONNECTOR_VIEW_BOX} 참고.
 * 채널 묶음 사이는 2px 띄운다.
 */
export default function EmbeddedResourceTable({ service, label, rows }: EmbeddedResourceTableProps) {
  const Logo = CONNECTOR_LOGOS[service];

  if (rows.length === 0) return <EmbeddingEmptyState />;

  return (
    // 고정 열 합(범위 180 + gap 16 + padding 24)조차 안 되는 슬롯에서만 스크롤로 흘린다
    <div className="overflow-x-auto">
      <table role="table" className="block w-full min-w-fit">
        <thead role="rowgroup" className="block">
          <tr role="row" className={cn(RESOURCE_ROW_GRID, 'min-h-9')}>
            {/* truncate: 좁은 슬롯에서 라벨이 두 줄로 접혀 헤더가 36을 넘는 걸 막는다 */}
            <th
              role="columnheader"
              scope="col"
              className="text-body-xsmall text-text-normal-alternative truncate text-left font-medium"
            >
              {label}
            </th>
            <th
              role="columnheader"
              scope="col"
              className="text-body-xsmall text-text-normal-alternative text-left font-medium whitespace-nowrap"
            >
              데이터 범위
            </th>
          </tr>
        </thead>

        {rows.map((row, groupIndex) => (
          <tbody role="rowgroup" key={row.id} className={cn('block', groupIndex > 0 && 'mt-0.5')}>
            <tr role="row" className={cn(RESOURCE_ROW_GRID, 'min-h-11.5')}>
              <td role="cell" className="flex min-w-0 items-center gap-2.5">
                <Logo className="size-5 shrink-0" />
                <span className="text-body-small text-text-normal-neutral truncate">{row.name}</span>
              </td>
              <td role="cell" className="text-body-small text-text-normal-assistive whitespace-nowrap">
                {row.dataRange}
              </td>
            </tr>

            {row.children?.map((child, childIndex, children) => {
              // 마지막 도큐먼트 아래로는 이어질 형제가 없으므로 세로선이 끊긴 에셋을 쓴다
              const isLast = childIndex === children.length - 1;
              const Connector = isLast ? IconConnectorLast : IconConnector;

              return (
                // 도큐먼트 행은 x22 — 행 padding 12에 10을 더한다
                <tr key={child.id} role="row" className={cn(RESOURCE_ROW_GRID, 'h-11.5 pl-5.5')}>
                  <td role="cell" className="flex min-w-0 items-center gap-2.5">
                    {/*
                     * 아이콘 47은 행 46보다 1 커야 연속된 도큐먼트의 세로선이 이어진다.
                     * 그대로 두면 행 높이(py 8 + 47 + 8)를 밀어올리므로, 형제 행의 로고와
                     * 같은 20짜리 자리만 차지하게 하고 아이콘은 그 위에 absolute 로 얹는다.
                     */}
                    <span aria-hidden="true" className="relative block h-5 w-3.5 shrink-0">
                      <Connector
                        viewBox={isLast ? LAST_CONNECTOR_VIEW_BOX : undefined}
                        className={cn('absolute top-1/2 left-0 h-11.75 -translate-y-1/2', isLast ? 'w-3.75' : 'w-3.5')}
                      />
                    </span>
                    <span className="text-body-small text-text-normal-neutral truncate">{child.name}</span>
                  </td>
                  <td role="cell" className="text-body-small text-text-normal-assistive whitespace-nowrap">
                    {child.dataRange}
                  </td>
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
    </div>
  );
}
