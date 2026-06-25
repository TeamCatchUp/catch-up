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
import type { PermissionMember } from '../../types/adminPermissionModel';

interface PermissionsTableProps {
  rows: PermissionMember[];
  onChangeRoleClick: (member: PermissionMember) => void;
  onRoleChangeClick: (member: PermissionMember) => void;
}

/** 권한 목록 테이블 */
export default function PermissionsTable({ rows, onChangeRoleClick, onRoleChangeClick }: PermissionsTableProps) {
  return (
    <section className="border-line-normal-neutral bg-fill-normal-normal flex min-h-0 flex-1 flex-col overflow-hidden border-y">
      <div className="border-line-normal-neutral bg-fill-normal-strong flex h-9 shrink-0 items-center border-b px-6 lg:px-9">
        <div className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-6 lg:gap-9">
          <span className="text-body-xsmall text-text-normal-alternative pl-1.5 text-left">이름</span>
          <span className="text-body-xsmall text-text-normal-alternative text-center">직급</span>
          <span className="text-body-xsmall text-text-normal-alternative text-center">부서</span>
          <span className="text-body-xsmall text-text-normal-alternative text-center">권한</span>
          <span aria-hidden className="block w-27.5" />
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="text-body-small text-text-normal-alternative flex h-full min-h-25 items-center justify-center">
          조회된 권한 정보가 없습니다.
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {rows.map((member) => {
            const roleLabel = ROLE_LABEL[member.role];

            return (
              <div
                key={member.id}
                className="border-line-normal-neutral flex h-12.5 shrink-0 items-center border-b px-6 lg:px-9"
              >
                <div className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-6 lg:gap-9">
                  <div className="flex items-center gap-4">
                    <DefaultProfile className="text-text-normal-assistive size-7.5 shrink-0 rounded-full" />
                    <span className="text-body-small text-text-normal-normal truncate">{member.name}</span>
                  </div>

                  <div className="flex items-center justify-center">
                    <span
                      className={cn(
                        TAG_BASE_CLASS,
                        RANK_BADGE_CLASS[JOB_LEVEL_LABEL[member.jobLevel]] ??
                          'bg-fill-normal-interaction-hover text-text-normal-alternative',
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
                          className="text-body-xsmall text-text-normal-normal max-w-full cursor-pointer truncate"
                        >
                          {member.department}
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        side="top"
                        align="center"
                        className="text-body-xsmall text-icon-normal-normal w-auto px-3 py-2"
                      >
                        {member.department}
                      </PopoverContent>
                    </Popover>
                  </div>

                  <div className="flex items-center justify-center">
                    <span className={cn(TAG_BASE_CLASS, ROLE_BADGE_CLASS[roleLabel])}>{roleLabel}</span>
                  </div>

                  <div className="flex w-27.5 items-center justify-end">
                    {member.role !== 'admin' ? (
                      <Button
                        variant="box-outline-gray"
                        size="sm"
                        className="h-7.5 w-27.5"
                        onClick={() => onChangeRoleClick(member)}
                      >
                        Admin 권한 부여
                      </Button>
                    ) : (
                      <Button
                        variant="box-outline-gray"
                        size="sm"
                        className="h-7.5 w-27.5"
                        onClick={() => onRoleChangeClick(member)}
                      >
                        권한 변경
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
}
