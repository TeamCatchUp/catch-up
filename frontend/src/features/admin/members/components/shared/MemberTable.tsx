import CheckboxChecked from '@/public/icons/icon/checkbox_checked.svg';
import CheckboxUnchecked from '@/public/icons/icon/checkbox_unchecked.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import { RANK_BADGE_CLASS, TAG_BASE_CLASS } from '../../constants/memberTableConfig';
import type { MemberTableRow } from '../../types/adminMember';

interface MemberTableProps {
  rows: MemberTableRow[];
  activeKey: string | null;
  onSelectKey: (key: string) => void;
  emptyMessage: string;
  /** 4번째 컬럼 헤더 (기본: '상태') */
  lastColumnHeader?: string;
  /** 4번째 컬럼 뱃지 스타일 맵 */
  lastColumnBadgeClass?: Record<string, string>;
  isSelecting?: boolean;
  selectedKeys?: Set<string>;
  onToggleKey?: (key: string) => void;
  onToggleAll?: () => void;
}

/** 좌측 이용자 테이블 (입장 신청 / 이용자 목록 공통) */
const MemberTable = ({
  rows,
  activeKey,
  onSelectKey,
  emptyMessage,
  lastColumnHeader = '상태',
  lastColumnBadgeClass = {},
  isSelecting,
  selectedKeys,
  onToggleKey,
  onToggleAll,
}: MemberTableProps) => {
  const allSelected = isSelecting && rows.length > 0 && selectedKeys?.size === rows.length;

  return (
    <section className="border-neutral-3 flex h-full min-h-0 flex-col overflow-clip border-r bg-white">
      {/* 헤더 */}
      <div
        className={cn(
          'border-neutral-3 bg-neutral-1 flex h-9 shrink-0 items-center border-b px-5',
          isSelecting && 'gap-3',
        )}
      >
        {isSelecting && (
          <button type="button" onClick={onToggleAll} className="shrink-0 cursor-pointer">
            <div className="p-1">
              {allSelected ? (
                <CheckboxChecked className="size-5" />
              ) : (
                <CheckboxUnchecked className="size-5" />
              )}
            </div>
          </button>
        )}
        <div className="grid flex-1 grid-cols-4 items-center">
          <span className="text-body-xsmall pl-7.5 text-left text-gray-50">이름</span>
          <span className="text-body-xsmall text-center text-gray-50">직급</span>
          <span className="text-body-xsmall text-center text-gray-50">부서</span>
          <span className="text-body-xsmall text-center text-gray-50">{lastColumnHeader}</span>
        </div>
      </div>

      {/* 행 */}
      {rows.length === 0 ? (
        <div className="text-body-small flex h-full min-h-25 items-center justify-center px-4 text-center text-gray-50">
          {emptyMessage}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
          {rows.map((row) => {
            const isActive = !isSelecting && activeKey === row.key;
            const isChecked = isSelecting && selectedKeys?.has(row.key);

            return (
              <button
                key={row.key}
                type="button"
                onClick={() => (isSelecting ? onToggleKey?.(row.key) : onSelectKey(row.key))}
                className={cn(
                  'border-neutral-3 flex h-12.5 shrink-0 cursor-pointer items-center border-b px-5 text-left',
                  isSelecting && 'gap-3',
                  isActive || isChecked ? 'bg-blue-1' : 'hover:bg-neutral-1 bg-white',
                )}
              >
                {isSelecting && (
                  <div className="shrink-0">
                    <div className="p-1">
                      {isChecked ? (
                        <CheckboxChecked className="size-5" />
                      ) : (
                        <CheckboxUnchecked className="size-5" />
                      )}
                    </div>
                  </div>
                )}
                <div className="grid flex-1 grid-cols-4 items-center">
                  {/* 이름 */}
                  <div className="flex items-center gap-4">
                    <DefaultProfile className="border-neutral-2 text-gray-30 size-7.5 shrink-0 rounded-full border" />
                    <span className="text-body-small text-gray-80 truncate">{row.name}</span>
                  </div>

                  {/* 직급 */}
                  <div className="flex items-center justify-center">
                    <span
                      className={cn(TAG_BASE_CLASS, RANK_BADGE_CLASS[row.rank] ?? 'bg-neutral-2 text-gray-50')}
                    >
                      {row.rank}
                    </span>
                  </div>

                  {/* 부서 */}
                  <div className="flex items-center justify-center">
                    <span className="text-body-xsmall text-gray-80 truncate">{row.department}</span>
                  </div>

                  {/* 4번째 컬럼 */}
                  <div className="flex items-center justify-center">
                    <span
                      className={cn(TAG_BASE_CLASS, lastColumnBadgeClass[row.lastColumn] ?? 'bg-neutral-2 text-gray-50')}
                    >
                      {row.lastColumn}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default MemberTable;
