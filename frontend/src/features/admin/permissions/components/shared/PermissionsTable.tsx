import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Button } from '@/shared/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import { RANK_BADGE_CLASS, ROLE_BADGE_CLASS, ROLE_LABEL, TAG_BASE_CLASS } from '../../constants/permissionsConfig';
import type { PermissionMember } from '../../types/adminPermission';

interface PermissionsTableProps {
  rows: PermissionMember[];
  onChangeRoleClick: (member: PermissionMember) => void;
}

/** 권한 목록 테이블 */
const PermissionsTable = ({ rows, onChangeRoleClick }: PermissionsTableProps) => {
  return (
    <section className="border-neutral-3 flex min-h-0 flex-1 flex-col overflow-hidden border-y bg-white">
      <div className="border-neutral-3 bg-neutral-1 flex h-9 shrink-0 items-center border-b px-6 lg:px-9">
        <div className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-6 lg:gap-9">
          <span className="text-body-xsmall pl-1.5 text-left text-gray-50">이름</span>
          <span className="text-body-xsmall text-center text-gray-50">직급</span>
          <span className="text-body-xsmall text-center text-gray-50">부서</span>
          <span className="text-body-xsmall text-center text-gray-50">권한</span>
          <span aria-hidden className="block w-[110px]" />
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="text-body-small flex h-full min-h-25 items-center justify-center text-gray-50">
          조회된 권한 정보가 없습니다.
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {rows.map((member) => {
            const roleLabel = ROLE_LABEL[member.role];

            return (
              <div key={member.id} className="border-neutral-3 flex h-12.5 shrink-0 items-center border-b px-6 lg:px-9">
                <div className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-6 lg:gap-9">
                  <div className="flex items-center gap-4">
                    <DefaultProfile className="border-neutral-2 text-gray-30 size-7.5 shrink-0 rounded-full border" />
                    <span className="text-body-small text-gray-80 truncate">{member.name}</span>
                  </div>

                  <div className="flex items-center justify-center">
                    <span className={cn(TAG_BASE_CLASS, RANK_BADGE_CLASS[member.rank] ?? 'bg-neutral-2 text-gray-50')}>
                      {member.rank}
                    </span>
                  </div>

                  <div className="flex items-center justify-center">
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className="text-body-xsmall text-gray-80 max-w-full cursor-pointer truncate"
                        >
                          {member.department}
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        side="top"
                        align="center"
                        className="text-body-xsmall text-gray-70 w-auto px-3 py-2"
                      >
                        {member.department}
                      </PopoverContent>
                    </Popover>
                  </div>

                  <div className="flex items-center justify-center">
                    <span className={cn(TAG_BASE_CLASS, ROLE_BADGE_CLASS[roleLabel])}>{roleLabel}</span>
                  </div>

                  <div className="flex w-[110px] items-center justify-end">
                    <Button
                      variant="box-outline-gray"
                      size="sm"
                      className="h-7.5 w-[110px]"
                      onClick={() => onChangeRoleClick(member)}
                    >
                      권한 변경
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default PermissionsTable;
