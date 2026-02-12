'use client';

import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { useUserStore } from '@/shared/store/userStore';
import { cn } from '@/shared/utils/cn';

import Profile from '/public/icons/icon/profile.svg';
import UnfoldMore from '/public/icons/icon/unfold_more.svg';

interface SideNavUserProps {
  isOpen: boolean;
}

export default function SideNavUser({ isOpen }: SideNavUserProps) {
  const user = useUserStore((state) => state.user);

  return (
    <div className="mt-auto flex flex-col gap-1.5">
      {isOpen && <div className="bg-neutral-3 relative right-2 h-px w-60" />}
      <Tooltip>
        <DropdownMenu>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  'flex h-13.5 cursor-pointer items-center rounded-lg',
                  isOpen
                    ? 'w-56.25 justify-between px-1.5 py-1 hover:bg-neutral-2 data-[state=open]:bg-neutral-2'
                    : 'justify-center',
                )}
              >
                <div className={cn('flex gap-4', isOpen ? 'mt-auto' : '')}>
                  <Profile className="border-neutral-2 h-10 w-10 rounded-xl border-[0.5px]" />
                  {isOpen && (
                    <div className="relative top-px max-w-31 text-left">
                      <div className="text-heading-small text-gray-80 truncate">{user?.name ?? '이름없음'}</div>
                      <div className="text-body-small truncate text-gray-50">{user?.email ?? ''}</div>
                    </div>
                  )}
                </div>
                {isOpen && (
                  <div className="bottom-1 flex items-center p-0.5">
                    <UnfoldMore className="h-6 w-6" />
                  </div>
                )}
              </button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          {!isOpen && (
            <TooltipContent side="right">
              <div className="flex flex-col">
                <span>{user?.name ?? '이름없음'}</span>
                <span>{user?.email ?? '역할없음'}</span>
              </div>
            </TooltipContent>
          )}
          <UserMenuContent userName={user?.name} userEmail={user?.email} />
        </DropdownMenu>
      </Tooltip>
    </div>
  );
}
