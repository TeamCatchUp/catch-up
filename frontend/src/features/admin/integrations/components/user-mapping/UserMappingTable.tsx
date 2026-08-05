import { Skeleton } from '@/shared/components/ui/skeleton';
import { cn } from '@/shared/utils/cn';

import { MAPPING_SOURCE_LABELS, MAPPING_SOURCES, type MappingSource, type UserMappingRow } from '../../types/userMappingModel';
import { MAPPING_ROW_GRID_FULL, MAPPING_ROW_GRID_SINGLE } from './userMappingTableGrid';
import UserMappingTableRow, { type UserMappingEditBinding } from './UserMappingTableRow';

interface UserMappingTableProps {
  rows: readonly UserMappingRow[];
  /** null이면 전체 4열, 값이 있으면 그 커넥터 1열 (통계 카드 탭 연동) */
  filterSource?: MappingSource | null;
  /** 로딩 스켈레톤 — 카피·형태는 구 UsersTable 승계 */
  isLoading?: boolean;
  /** 스켈레톤 행 수. 페이지 사이즈와 일치시키면 height shift 0 */
  skeletonCount?: number;
  /** 있으면 커넥터 셀이 계정 선택 드롭다운으로 바뀐다(구버전 `17379:92742` 패턴) */
  edit?: UserMappingEditBinding;
}

/**
 * 이용자 매핑 표 — 전체 4열 / 커넥터 필터 1열.
 *
 * table 엘리먼트 + 행 grid. display를 grid로 덮으면 표 시맨틱이 사라지므로
 * `role`을 되살린다(임베딩 표와 같은 처리). 행 렌더링(셀 값 3종·수정 모드 분기)은
 * {@link UserMappingTableRow}가, 빈 상태 배너는 `MappingSyncNotice`가 담당한다 —
 * 이 표는 rows가 비면 헤더만 남긴다.
 */
export default function UserMappingTable({
  rows,
  filterSource = null,
  isLoading = false,
  skeletonCount = 10,
  edit,
}: UserMappingTableProps) {
  const sources: readonly MappingSource[] = filterSource ? [filterSource] : MAPPING_SOURCES;
  const rowGrid = filterSource ? MAPPING_ROW_GRID_SINGLE : MAPPING_ROW_GRID_FULL;

  return (
    // 고정 열 하한(점 8 + 사용자 140 + 커넥터 최소폭)이 안 되는 슬롯에서만 스크롤로 흘린다
    <div className="overflow-x-auto">
      <table role="table" className="block w-full min-w-fit">
        <thead role="rowgroup" className="block">
          <tr role="row" className={cn(rowGrid, 'bg-fill-normal-strong min-h-9 rounded-lg')}>
            <th role="columnheader" scope="col">
              <span className="sr-only">연동 상태</span>
            </th>
            <th role="columnheader" scope="col" className="text-body-xsmall text-text-normal-neutral truncate text-left">
              Keycloak 사용자
            </th>
            {sources.map((source) => (
              <th
                key={source}
                role="columnheader"
                scope="col"
                className="text-body-xsmall text-text-normal-neutral truncate text-left"
              >
                {MAPPING_SOURCE_LABELS[source]}
              </th>
            ))}
          </tr>
        </thead>

        <tbody role="rowgroup" className="block">
          {isLoading
            ? Array.from({ length: skeletonCount }).map((_, index) => (
                <tr
                  key={`skeleton-${index}`}
                  role="row"
                  className={cn(rowGrid, 'border-line-normal-neutral min-h-16.5 border-b py-3')}
                >
                  <td role="cell" />
                  <td role="cell">
                    <Skeleton className="h-5 w-24" />
                  </td>
                  {sources.map((source) => (
                    <td key={source} role="cell">
                      <Skeleton className="h-10 w-full max-w-41.25" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <UserMappingTableRow key={row.id} row={row} sources={sources} rowGrid={rowGrid} edit={edit} />
              ))}
        </tbody>
      </table>
    </div>
  );
}
