import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import CheckboxIcon from '@/shared/components/ui/checkboxIcon';
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
    <section className="border-edge-neutral bg-fill-normal flex h-full min-h-0 flex-col overflow-clip border-r">
      {/* 헤더 */}
      <div
        className={cn(
          'border-edge-neutral bg-fill-strong flex h-9 shrink-0 items-center border-b px-5',
          isSelecting && 'gap-3',
        )}
      >
        {isSelecting && (
          <button type="button" onClick={onToggleAll} className="shrink-0 cursor-pointer">
            <CheckboxIcon checked={!!allSelected} className="size-5" />
          </button>
        )}
        <div className="grid flex-1 grid-cols-4 items-center">
          <span className="text-body-xsmall text-content-alternative pl-7.5 text-left">이름</span>
          <span className="text-body-xsmall text-content-alternative text-center">직급</span>
          <span className="text-body-xsmall text-content-alternative text-center">부서</span>
          <span className="text-body-xsmall text-content-alternative text-center">{lastColumnHeader}</span>
        </div>
      </div>

      {/* 행 */}
      {rows.length === 0 ? (
        <div className="text-body-small text-content-alternative flex h-full min-h-25 items-center justify-center px-4 text-center">
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
                  'border-edge-neutral flex h-12.5 shrink-0 cursor-pointer items-center border-b px-5 text-left',
                  isSelecting && 'gap-3',
                  isActive || isChecked ? 'bg-fill-primary-assistive' : 'hover:bg-fill-strong bg-fill-normal',
                )}
              >
                {isSelecting && <CheckboxIcon checked={!!isChecked} className="size-5" />}
                <div className="grid flex-1 grid-cols-4 items-center">
                  {/* 이름 */}
                  <div className="flex items-center gap-4">
                    <DefaultProfile className="text-content-assistive size-7.5 shrink-0 rounded-full" />
                    <span className="text-body-small text-content-normal truncate">{row.name}</span>
                  </div>

                  {/* 직급 */}
                  <div className="flex items-center justify-center">
                    <span
                      className={cn(
                        TAG_BASE_CLASS,
                        RANK_BADGE_CLASS[row.rank] ?? 'bg-fill-interaction-hover text-content-alternative',
                      )}
                    >
                      {row.rank}
                    </span>
                  </div>

                  {/* 부서 */}
                  <div className="flex items-center justify-center">
                    <span className="text-body-xsmall text-content-normal truncate">{row.department}</span>
                  </div>

                  {/* 4번째 컬럼 */}
                  <div className="flex items-center justify-center">
                    <span
                      className={cn(
                        TAG_BASE_CLASS,
                        lastColumnBadgeClass[row.lastColumn] ?? 'bg-fill-interaction-hover text-content-alternative',
                      )}
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
