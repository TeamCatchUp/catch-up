/**
 * SideNavMenu
 * 사이드바 메뉴 아이템 (홈, AI, 수신함, 설정)
 */

'use client';

import { usePathname, useRouter } from 'next/navigation';

import AI from '@/public/icons/icon/ai.svg';
import Home from '@/public/icons/icon/home.svg';
// TODO: 수신함 기능 활성화 시 Inbox import 복원
// import Inbox from '@/public/icons/icon/inbox.svg';
import Settings from '@/public/icons/icon/settings.svg';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

// TODO: 수신함 기능 활성화 시 UNREAD_COUNT 복원

/** 메뉴 아이템 정의 (href: 페이지 이동, panel: 사이드 패널 토글) */
const navItems = [
  { name: '홈', href: '/', Icon: Home, tooltipOpen: '최근 업무 보기', tooltipClosed: '홈' },
  {
    name: '캐치스턴트 AI',
    href: '/search',
    Icon: AI,
    tooltipOpen: '사내 지식 물어보기',
    tooltipClosed: '캐치스턴트 AI',
  },
  // TODO: 수신함 기능 임시 비활성화
  // { name: '수신함', panel: 'inbox' as const, Icon: Inbox, tooltipOpen: '수신함', tooltipClosed: '수신함' },
  { name: '설정', panel: 'settings' as const, Icon: Settings, tooltipOpen: '설정', tooltipClosed: '설정' },
];

// 메뉴 상태별 스타일
const defaultClass = 'bg-fill-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed active:ring-1 active:ring-edge-neutral';
const selectedClass = 'ring-1 ring-edge-assistive bg-fill-primary-assistive hover:bg-fill-primary-interaction-hover-assistive';

interface SideNavMenuProps {
  isOpen: boolean;
}

export default function SideNavMenu({ isOpen }: SideNavMenuProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { activePanel, setActivePanel } = useSidebarStore();

  return (
    <div className={`flex flex-col ${isOpen ? 'gap-1' : 'gap-2'}`}>
      {navItems.map((item) => {
        const isActive = item.href ? pathname === item.href : activePanel === item.panel;

        const handleClick = () => {
          if (item.panel) {
            // TODO: 수신함 등 다른 패널 활성화 시 패널별 분기 추가
            setActivePanel(null);
            router.push(useSidebarStore.getState().lastSettingsPath);
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
                      isActive ? 'text-blue-50 group-hover:text-blue-50' : 'text-icon-normal',
                    )}
                  />
                  {isOpen && (
                    <span
                      className={cn(
                        'text-body-small relative flex-1 text-left',
                        isActive ? 'text-blue-55 group-hover:text-blue-55' : 'text-content-normal',
                      )}
                    >
                      {item.name}
                    </span>
                  )}
                  {/* TODO: 수신함 기능 활성화 시 배지 복원 */}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">{isOpen ? item.tooltipOpen : item.tooltipClosed}</TooltipContent>
            </Tooltip>
          </div>
        );
      })}
    </div>
  );
}
