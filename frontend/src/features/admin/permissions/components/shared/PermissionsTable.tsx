import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Button } from '@/shared/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import {
  JOB_LEVEL_LABEL,
  RANK_BADGE_CLASS,
  ROLE_BADGE_CLASS,
  ROLE_LABEL,
  TAG_BASE_CLASS,
} from '../../constants/permissionsConfig';
import type { PermissionMember } from '../../types/adminPermission';

interface PermissionsTableProps {
  rows: PermissionMember[];
  onChangeRoleClick: (member: PermissionMember) => void;
}

/** 권한 목록 테이블 */
const PermissionsTable = ({ rows, onChangeRoleClick }: PermissionsTableProps) => {
  return (
    <section className="border-edge-neutral bg-fill-normal flex min-h-0 flex-1 flex-col overflow-hidden border-y">
      <div className="border-edge-neutral bg-fill-strong flex h-9 shrink-0 items-center border-b px-6 lg:px-9">
        <div className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-6 lg:gap-9">
          <span className="text-body-xsmall text-content-alternative pl-1.5 text-left">이름</span>
          <span className="text-body-xsmall text-content-alternative text-center">직급</span>
          <span className="text-body-xsmall text-content-alternative text-center">부서</span>
          <span className="text-body-xsmall text-content-alternative text-center">권한</span>
          <span aria-hidden className="block w-[110px]" />
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="text-body-small text-content-alternative flex h-full min-h-25 items-center justify-center">
          조회된 권한 정보가 없습니다.
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {rows.map((member) => {
            const roleLabel = ROLE_LABEL[member.role];

            return (
              <div
                key={member.id}
                className="border-edge-neutral flex h-12.5 shrink-0 items-center border-b px-6 lg:px-9"
              >
                <div className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-6 lg:gap-9">
                  <div className="flex items-center gap-4">
                    <DefaultProfile className="text-content-assistive size-7.5 shrink-0 rounded-full" />
                    <span className="text-body-small text-content-normal truncate">{member.name}</span>
                  </div>

                  <div className="flex items-center justify-center">
                    <span
                      className={cn(
                        TAG_BASE_CLASS,
                        RANK_BADGE_CLASS[JOB_LEVEL_LABEL[member.jobLevel]] ??
                          'bg-fill-interaction-hover text-content-alternative',
                      )}
                    >
                      {JOB_LEVEL_LABEL[member.jobLevel]}
                    </span>
                  </div>

                  <div className="flex items-center justify-center">
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className="text-body-xsmall text-content-normal max-w-full cursor-pointer truncate"
                        >
                          {member.department}
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        side="top"
                        align="center"
                        className="text-body-xsmall text-icon-normal w-auto px-3 py-2"
                      >
                        {member.department}
                      </PopoverContent>
                    </Popover>
                  </div>

                  <div className="flex items-center justify-center">
                    <span className={cn(TAG_BASE_CLASS, ROLE_BADGE_CLASS[roleLabel])}>{roleLabel}</span>
                  </div>

                  <div className="flex w-[110px] items-center justify-end">
                    {member.role !== 'admin' && (
                      <Button
                        variant="box-outline-gray"
                        size="sm"
                        className="h-7.5 w-[110px]"
                        onClick={() => onChangeRoleClick(member)}
                      >
                        Admin 권한 부여
                      </Button>
                    )}
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
