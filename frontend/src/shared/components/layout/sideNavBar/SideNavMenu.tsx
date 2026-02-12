'use client';

import { usePathname, useRouter } from 'next/navigation';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

import AI from '/public/icons/icon/ai.svg';
import Home from '/public/icons/icon/home.svg';
import Inbox from '/public/icons/icon/inbox.svg';
import Settings from '/public/icons/icon/settings.svg';

const UNREAD_COUNT = 3; // mock

const navItems = [
  { name: '홈', href: '/', Icon: Home, tooltipOpen: '최근 업무 보기', tooltipClosed: '홈' },
  { name: '캐치스턴트 AI', href: '/search', Icon: AI, tooltipOpen: '사내 지식 물어보기', tooltipClosed: '캐치스턴트 AI' },
  { name: '수신함', panel: 'inbox' as const, Icon: Inbox, tooltipOpen: '수신함', tooltipClosed: '수신함' },
  { name: '설정', panel: 'settings' as const, Icon: Settings, tooltipOpen: '설정', tooltipClosed: '설정' },
];

const defaultClass =
  'bg-white hover:bg-neutral-2 active:bg-neutral-3 active:ring-1 active:ring-neutral-3';
const selectedClass = 'ring-1 ring-neutral-2 bg-blue-1 hover:bg-blue-5';

interface SideNavMenuProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

export default function SideNavMenu({ isOpen, setIsOpen }: SideNavMenuProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { activePanel, togglePanel, setActivePanel } = useSidebarStore();

  return (
    <div className={`flex flex-col ${isOpen ? 'gap-1' : 'gap-2'}`}>
      {navItems.map((item) => {
        const isActive = item.href
          ? pathname === item.href
          : activePanel === item.panel;

        const handleClick = () => {
          if (item.panel) {
            if (item.panel === 'settings' && isOpen) setIsOpen(false);
            togglePanel(item.panel);
          } else {
            setActivePanel(null);
            router.push(item.href!);
          }
        };

        return (
          <div key={item.name} className="group relative">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={handleClick}
                  className={cn(
                    'relative flex h-10 cursor-pointer items-center rounded-lg',
                    isActive ? selectedClass : defaultClass,
                    isOpen ? 'w-full gap-3 px-2.5 py-2' : 'w-10 items-center justify-center',
                  )}
                >
                  <item.Icon
                    className={cn(
                      isOpen ? 'h-6 w-6' : 'h-7 w-7',
                      isActive ? 'text-blue-50 group-hover:text-blue-50' : 'text-gray-70',
                    )}
                  />
                  {isOpen && (
                    <span
                      className={cn(
                        'text-left text-body-small relative flex-1',
                        isActive ? 'text-blue-55 group-hover:text-blue-55' : 'text-gray-80',
                      )}
                    >
                      {item.name}
                    </span>
                  )}
                  {/* 수신함 배지 (열림) */}
                  {isOpen && item.panel === 'inbox' && UNREAD_COUNT > 0 && (
                    <span className="bg-blue-1 border-blue-40 text-blue-40 text-body-small min-w-[23px] rounded-md border-[0.5px] px-0.5 text-center">
                      {UNREAD_COUNT}
                    </span>
                  )}
                  {/* 수신함 blue dot (닫힘) */}
                  {!isOpen && item.panel === 'inbox' && UNREAD_COUNT > 0 && (
                    <span className="bg-blue-40 absolute right-1 top-1.25 h-1.5 w-1.5 rounded-full" />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {isOpen ? item.tooltipOpen : item.tooltipClosed}
              </TooltipContent>
            </Tooltip>
          </div>
        );
      })}
    </div>
  );
}
