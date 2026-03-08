'use client';

import GroupAdd from '@/public/icons/icon/group_add.svg';
import Settings from '@/public/icons/icon/settings.svg';
import { DropdownMenuContent, DropdownMenuItem } from '@/shared/components/ui/dropdown-menu';

export function TeamSpaceMoreContent() {
  return (
    <DropdownMenuContent
      side="right"
      align="start"
      sideOffset={8}
      className="w-62.5"
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <GroupAdd className="text-icon-normal h-6 w-6" />
        <span>팀원 추가</span>
      </DropdownMenuItem>
      <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
        <Settings className="text-icon-normal h-6 w-6" />
        <span>팀스페이스 설정</span>
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}
