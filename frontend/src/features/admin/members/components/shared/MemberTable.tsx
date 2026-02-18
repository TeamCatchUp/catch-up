import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import {
  DEPT_BADGE_CLASS,
  RANK_BADGE_CLASS,
  ROLE_BADGE_CLASS,
  TAG_BASE_CLASS,
} from '../../constants/memberTableConfig';
import type { MemberTableRow } from '../../types/adminMember';

interface MemberTableProps {
  rows: MemberTableRow[];
  activeKey: string | null;
  onSelectKey: (key: string) => void;
  emptyMessage: string;
}

/** 좌측 이용자 테이블 (입장 신청 / 이용자 목록 공통) */
const MemberTable = ({ rows, activeKey, onSelectKey, emptyMessage }: MemberTableProps) => {
  return (
    <section className="border-neutral-3 flex h-full min-h-0 flex-col overflow-clip border-r bg-white">
      {/* 헤더 */}
      <div className="border-neutral-3 bg-neutral-1 grid h-9 shrink-0 grid-cols-4 items-center border-b px-5">
        <span className="text-body-xsmall pl-7.5 text-left text-gray-50">이름</span>
        <span className="text-body-xsmall text-center text-gray-50">직급</span>
        <span className="text-body-xsmall text-center text-gray-50">부서</span>
        <span className="text-body-xsmall text-center text-gray-50">권한</span>
      </div>

      {/* 행 */}
      {rows.length === 0 ? (
        <div className="text-body-small flex h-full min-h-25 items-center justify-center px-4 text-center text-gray-50">
          {emptyMessage}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
          {rows.map((row) => {
            const isSelected = activeKey === row.key;

            return (
              <button
                key={row.key}
                type="button"
                onClick={() => onSelectKey(row.key)}
                className={cn(
                  'border-neutral-3 grid h-12.5 shrink-0 cursor-pointer grid-cols-4 items-center border-b px-5 text-left',
                  isSelected ? 'bg-blue-1' : 'hover:bg-neutral-1 bg-white',
                )}
              >
                {/* 이름 */}
                <div className="flex items-center gap-4">
                  <DefaultProfile className="border-neutral-2 text-gray-30 size-7.5 shrink-0 rounded-full border" />
                  <span className="text-body-small text-gray-80 truncate">{row.name}</span>
                </div>

                {/* 직급 */}
                <div className="flex items-center justify-center">
                  <span className={cn(TAG_BASE_CLASS, RANK_BADGE_CLASS[row.rank] ?? 'bg-neutral-2 text-gray-50')}>
                    {row.rank}
                  </span>
                </div>

                {/* 부서 */}
                <div className="flex items-center justify-center">
                  <span className={cn(TAG_BASE_CLASS, DEPT_BADGE_CLASS)}>{row.department}</span>
                </div>

                {/* 권한 */}
                <div className="flex items-center justify-center">
                  <span className={cn(TAG_BASE_CLASS, ROLE_BADGE_CLASS[row.role] ?? 'bg-neutral-2 text-gray-50')}>
                    {row.role}
                  </span>
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
