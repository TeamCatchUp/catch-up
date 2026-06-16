/**
 * SideNavMenu
 * 사이드바 메뉴 아이템 (홈, 캐치스턴트 AI, 문서 탐색, 설정, 에이전트)
 */

'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import AI from '@/public/icons/icon/ai.svg';
import DocumentSearch from '@/public/icons/icon/document_search.svg';
import DocumentSearchFilled from '@/public/icons/icon/document_search_filled.svg';
import Home from '@/public/icons/icon/home.svg';
import Lightbulb from '@/public/icons/icon/lightbulb.svg';
// TODO: 수신함 기능 활성화 시 Inbox import 복원
// import Inbox from '@/public/icons/icon/inbox.svg';
import Settings from '@/public/icons/icon/settings.svg';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

// TODO: 수신함 기능 활성화 시 UNREAD_COUNT 복원

type NavMatch = 'home' | 'search' | 'docs' | 'settings' | 'agentStudio';
type NavGroup = 'primary' | 'agent';

interface NavItem {
  name: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  // 활성 시 사용할 filled 아이콘 (선택)
  IconActive?: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  href?: string;
  panel?: 'settings';
  match: NavMatch;
  tooltipOpen: string;
  tooltipClosed: string;
  beta?: boolean;
  group: NavGroup;
}

/** 메뉴 아이템 정의 (href: 페이지 이동, panel: 사이드 패널 토글) */
const navItems: NavItem[] = [
  {
    name: '홈',
    href: '/',
    Icon: Home,
    match: 'home',
    tooltipOpen: '최근 업무 보기',
    tooltipClosed: '홈',
    group: 'primary',
  },
  {
    name: '캐치스턴트 AI',
    href: '/search',
    Icon: AI,
    match: 'search',
    tooltipOpen: '사내 지식 물어보기',
    tooltipClosed: '캐치스턴트 AI',
    group: 'primary',
  },
  {
    name: '문서 탐색',
    href: '/?mode=docs',
    Icon: DocumentSearch,
    IconActive: DocumentSearchFilled,
    match: 'docs',
    tooltipOpen: '문서 탐색',
    tooltipClosed: '문서 탐색',
    beta: true,
    group: 'primary',
  },
  // TODO: 수신함 기능 임시 비활성화
  // { name: '수신함', panel: 'inbox' as const, Icon: Inbox, ... },
  {
    name: '설정',
    panel: 'settings',
    Icon: Settings,
    match: 'settings',
    tooltipOpen: '설정',
    tooltipClosed: '설정',
    group: 'primary',
  },
  {
    name: '에이전트 스튜디오',
    href: '/agent-studio',
    Icon: Lightbulb,
    match: 'agentStudio',
    tooltipOpen: '에이전트 스튜디오',
    tooltipClosed: '에이전트 스튜디오',
    group: 'agent',
  },
];

// URL + mode + activePanel을 기준으로 활성 메뉴 결정
function resolveActiveMatch(pathname: string, mode: string | null, activePanel: string | null): NavMatch | null {
  if (activePanel === 'settings') return 'settings';
  if (pathname.startsWith('/agent-studio')) return 'agentStudio';
  if (mode === 'docs') return 'docs';
  if (pathname === '/search') return 'search';
  if (pathname === '/') return 'home';
  return null;
}

// 메뉴 상태별 스타일
const defaultClass =
  'border border-transparent hover:bg-fill-normal-interaction-hover hover:border-line-normal-assistive active:bg-fill-normal-interaction-pressed active:border-line-normal-neutral';
const selectedClass = 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive';

interface SideNavMenuProps {
  isOpen: boolean;
}

export default function SideNavMenu({ isOpen }: SideNavMenuProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { activePanel, setActivePanel } = useSidebarStore();

  const activeMatch = resolveActiveMatch(pathname, searchParams.get('mode'), activePanel);
  const primaryItems = navItems.filter((item) => item.group === 'primary');
  const agentItems = navItems.filter((item) => item.group === 'agent');

  const renderNavItems = (items: NavItem[]) =>
    items.map((item) => {
      const isActive = item.match === activeMatch;
      const IconComponent = isActive && item.IconActive ? item.IconActive : item.Icon;

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
                aria-label={isOpen ? undefined : item.name}
                className={cn(
                  'relative flex cursor-pointer items-center',
                  isActive ? selectedClass : defaultClass,
                  isOpen ? 'h-9 w-full gap-3 rounded-lg px-2.5 py-1.5' : 'size-9 justify-center rounded-xl p-1',
                )}
              >
                <IconComponent
                  className={cn(
                    isOpen ? 'size-5.5' : 'size-6.5',
                    isActive
                      ? 'text-icon-primary-normal group-hover:text-icon-primary-normal'
                      : 'text-icon-normal-normal',
                  )}
                />
                {isOpen && (
                  <span
                    className={cn(
                      'text-body-small relative flex-1 text-left',
                      isActive
                        ? 'text-text-primary-normal group-hover:text-text-primary-normal'
                        : 'text-text-normal-normal',
                    )}
                  >
                    {item.name}
                  </span>
                )}
                {isOpen && item.beta && (
                  <span className="bg-fill-normal-interaction-hover text-text-normal-alternative inline-flex h-5 items-center justify-center gap-1 rounded-md px-1 py-0.5 text-[12px] leading-[1.5] font-medium">
                    베타
                  </span>
                )}
                {/* TODO: 수신함 기능 활성화 시 배지 복원 */}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">{isOpen ? item.tooltipOpen : item.tooltipClosed}</TooltipContent>
          </Tooltip>
        </div>
      );
    });

  return (
    <div className={cn('flex flex-col', isOpen ? 'gap-5' : 'gap-1.5')}>
      <div className={cn('flex flex-col', isOpen ? 'gap-0' : 'gap-1.5')}>{renderNavItems(primaryItems)}</div>
      <div className={cn('flex flex-col', isOpen ? 'gap-1' : 'gap-1.5')}>
        {isOpen && (
          <div className="flex h-5 items-center gap-1.5 px-2.5">
            <span className="text-body-xsmall text-text-normal-alternative">에이전트</span>
            <span className="bg-fill-normal-interaction-hover text-text-normal-alternative inline-flex h-5 items-center justify-center rounded-md px-1 text-[12px] leading-[1.5] font-medium">
              베타
            </span>
          </div>
        )}
        {renderNavItems(agentItems)}
      </div>
    </div>
  );
}
