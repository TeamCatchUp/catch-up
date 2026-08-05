import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import type { AccountOption, AccountOverride } from '../../hooks/useUserMappingEdit';
import type { MappingAccount, MappingCellValue, MappingSource, UserMappingRow } from '../../types/userMappingModel';
import AccountSelectDropdown from './AccountSelectDropdown';

/** 수정 모드에서 셀을 드롭다운으로 바꾸기 위한 배선 (구 UsersStatusSection 승계) */
export interface UserMappingEditBinding {
  optionsByService: Partial<Record<MappingSource, AccountOption[]>>;
  /** 셀에 걸린 로컬 변경 — 없으면 서버 값을 그대로 보여준다 */
  overrideOf: (rowId: string, source: MappingSource) => AccountOverride | undefined;
  onSelectAccount: (rowId: string, source: MappingSource, account: AccountOption) => void;
  onToggleUnused: (rowId: string, source: MappingSource, unused: boolean) => void;
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

/** 커넥터 계정 셀 — 아바타+이름 / 이메일 2줄 */
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

/** 수정 셀 상태 — 로컬 override가 서버 값보다 우선한다 */
const resolveEditCell = (
  override: AccountOverride | undefined,
  value: MappingCellValue,
): { account: AccountOption | undefined; unused: boolean } => {
  if (override?.type === 'account') return { account: override.account, unused: false };
  if (override?.type === 'unused') return { account: undefined, unused: true };
  if (value === 'unused') return { account: undefined, unused: true };
  if (value) {
    // 서버 값에는 계정 id가 없다 — 드롭다운 표시용이라 빈 id로 채운다
    return {
      account: { id: '', name: value.name, identifier: value.identifier, picture: value.picture ?? null },
      unused: false,
    };
  }
  return { account: undefined, unused: false };
};

interface UserMappingTableRowProps {
  row: UserMappingRow;
  sources: readonly MappingSource[];
  /** 행 grid 템플릿 — 표 전체와 열이 어긋나지 않게 표가 내려준다 */
  rowGrid: string;
  edit?: UserMappingEditBinding;
}

/** 이용자 매핑 표의 한 행 — 상태 점 + 사용자 + 커넥터 셀(보기/수정) */
export default function UserMappingTableRow({ row, sources, rowGrid, edit }: UserMappingTableRowProps) {
  return (
    <tr role="row" className={cn(rowGrid, 'border-line-normal-neutral min-h-16.5 border-b py-3')}>
      {/* 상태 점 — 전부 연동 녹색 / 일부 미연동 적색 */}
      <td role="cell">
        <span
          className={cn('block size-2 rounded-full', row.fullyMapped ? 'bg-status-positive' : 'bg-status-destructive')}
        >
          <span className="sr-only">{row.fullyMapped ? '전체 연동됨' : '일부 미연동'}</span>
        </span>
      </td>

      <td role="cell" className="flex min-w-0 items-center gap-3">
        <Avatar picture={row.user.picture} />
        <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate">{row.user.name}</span>
      </td>

      {sources.map((source) => {
        const value = row.accounts[source] ?? null;

        if (edit) {
          const { account, unused } = resolveEditCell(edit.overrideOf(row.id, source), value);
          return (
            <td key={source} role="cell" className="min-w-0">
              <AccountSelectDropdown
                status={unused ? '미사용' : '미등록'}
                options={edit.optionsByService[source] ?? []}
                selectedAccount={account}
                onSelect={(next) => edit.onSelectAccount(row.id, source, next)}
                onToggleUnused={(next) => edit.onToggleUnused(row.id, source, next)}
              />
            </td>
          );
        }

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
  );
}
