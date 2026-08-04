import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { cn } from '@/shared/utils/cn';

import {
  MAPPING_SOURCE_LABELS,
  MAPPING_SOURCES,
  type MappingAccount,
  type MappingSource,
  type UserMappingRow,
} from './userMappingModel';
import { MAPPING_ROW_GRID_FULL, MAPPING_ROW_GRID_SINGLE } from './userMappingTableGrid';

interface UserMappingTableProps {
  rows: readonly UserMappingRow[];
  /** null이면 전체 4열, 값이 있으면 그 커넥터 1열 (통계 카드 탭 연동) */
  filterSource?: MappingSource | null;
  /** 로딩 스켈레톤 — 카피·형태는 구 UsersTable 승계 */
  isLoading?: boolean;
  /** 스켈레톤 행 수. 페이지 사이즈와 일치시키면 height shift 0 */
  skeletonCount?: number;
}

const Avatar = ({ picture, className }: { picture?: string | null; className?: string }) =>
  picture ? (
    <Image
      src={picture}
      alt=""
      width={20}
      height={20}
      className={cn('border-fill-normal-strong size-5 shrink-0 rounded-full border', className)}
    />
  ) : (
    <DefaultProfile
      className={cn('border-fill-normal-strong text-text-normal-assistive size-5 shrink-0 rounded-full border', className)}
    />
  );

/** 커넥터 계정 셀 — 아바타+이름 / 이메일 2줄. Figma `17060:75378` (셀 max 165) */
function AccountCell({ account }: { account: MappingAccount }) {
  return (
    <div className="flex max-w-41.25 min-w-0 flex-col gap-0.5">
      <div className="flex w-full items-center gap-2">
        <Avatar picture={account.picture} />
        <span className="text-body-xsmall text-text-normal-normal min-w-0 flex-1 truncate">{account.name}</span>
      </div>
      <span className="text-body-xsmall text-text-normal-alternative w-full truncate">{account.identifier}</span>
    </div>
  );
}

/**
 * 이용자 매핑 표.
 * Figma `17060:75363`(전체 4열) · `17379:78332`(커넥터 필터 1열).
 *
 * table 엘리먼트 + 행 grid — 열 폭은 {@link MAPPING_ROW_GRID_FULL} /
 * {@link MAPPING_ROW_GRID_SINGLE}이 정한다. display를 grid로 덮으면 표 시맨틱이
 * 사라지므로 `role`을 되살린다(임베딩 표와 같은 처리).
 *
 * 셀 값 3종: 계정(2줄) / "미사용" 태그 / 미연동 "-".
 * 빈 상태 배너("CSV 파일을 업로드해주세요!")는 표 밖 요소라 `MappingSyncNotice`가
 * 담당한다 — 이 표는 rows가 비면 헤더만 남긴다.
 */
export default function UserMappingTable({
  rows,
  filterSource = null,
  isLoading = false,
  skeletonCount = 10,
}: UserMappingTableProps) {
  const sources: readonly MappingSource[] = filterSource ? [filterSource] : MAPPING_SOURCES;
  const rowGrid = filterSource ? MAPPING_ROW_GRID_SINGLE : MAPPING_ROW_GRID_FULL;

  return (
    // 고정 열 하한(점 8 + 사용자 140 + 커넥터 최소폭)이 안 되는 슬롯에서만 스크롤로 흘린다
    <div className="overflow-x-auto">
      <table role="table" className="block w-full min-w-fit">
        <thead role="rowgroup" className="block">
          {/* 헤더 36 — fill/normal/strong 배경, 13px text/normal/neutral */}
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
                <tr key={`skeleton-${index}`} role="row" className={cn(rowGrid, 'border-line-normal-neutral min-h-16.5 border-b py-3')}>
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
                <tr key={row.id} role="row" className={cn(rowGrid, 'border-line-normal-neutral min-h-16.5 border-b py-3')}>
                  {/* 상태 점 — 전부 연동 녹색 / 일부 미연동 적색 */}
                  <td role="cell">
                    <span
                      className={cn(
                        'block size-2 rounded-full',
                        row.fullyMapped ? 'bg-status-positive' : 'bg-status-destructive',
                      )}
                    >
                      <span className="sr-only">{row.fullyMapped ? '전체 연동됨' : '일부 미연동'}</span>
                    </span>
                  </td>

                  <td role="cell" className="flex min-w-0 items-center gap-3">
                    <Avatar picture={row.user.picture} />
                    <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate">
                      {row.user.name}
                    </span>
                  </td>

                  {sources.map((source) => {
                    const value = row.accounts[source] ?? null;
                    return (
                      <td key={source} role="cell" className="min-w-0">
                        {value === 'unused' ? (
                          <span className="bg-fill-normal-strong text-body-xsmall text-text-normal-alternative rounded-md2 inline-flex px-1.5 py-0.5">
                            미사용
                          </span>
                        ) : value ? (
                          <AccountCell account={value} />
                        ) : (
                          <span className="text-body-xsmall text-text-normal-assistive">-</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  );
}
