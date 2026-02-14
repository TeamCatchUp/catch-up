'use client';

import Link from 'next/link';

import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';

import { MoreButtonContent } from './MoreButtonModal';

import Settings from '/public/icons/icon/admin_panel_settings.svg';
import AI from '/public/icons/icon/ai.svg';
import Home from '/public/icons/icon/home.svg';
import Kebeb_2 from '/public/icons/icon/kebeb 2.svg';
import MyPage from '/public/icons/icon/person.svg';

type PageType = 'home' | 'search' | 'mypage' | 'settings';

interface PageConfig {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href: string;
}

const pageConfigs: Record<PageType, PageConfig> = {
  home: {
    icon: Home,
    label: '홈',
    href: '/',
  },
  search: {
    icon: AI,
    label: '캐치스턴트 AI',
    href: '/search',
  },
  mypage: {
    icon: MyPage,
    label: '마이페이지',
    href: '/mypage/settings',
  },
  settings: {
    icon: Settings,
    label: '권한 설정',
    href: '/settings',
  },
};

interface TopNavbarProps {
  pageType: PageType;
}

const TopNavbar = ({ pageType }: TopNavbarProps) => {
  const config = pageConfigs[pageType];
  const IconComponent = config.icon;

  return (
    <nav aria-label="메인 네비게이션" className="border-neutral-3 sticky top-0 z-50 h-full w-full border-b bg-white">
      <div className="flex justify-between px-16 py-2">
        <div className="flex items-center justify-center">
          <Link href={config.href} className="text-gray-80 flex cursor-pointer gap-2">
            <IconComponent className="h-6 w-6" />
            <span className="text-heading-medium relative top-[0.5px]">{config.label}</span>
          </Link>
        </div>
        <ul className="flex items-center justify-center gap-2">
          <li>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 data-[state=open]:border-neutral-4 data-[state=open]:bg-neutral-2 cursor-pointer rounded-lg border bg-white px-1.5 py-1.5 transition-colors">
                  <Kebeb_2 className="text-gray-70 h-6 w-6" />
                </button>
              </DropdownMenuTrigger>
              <MoreButtonContent />
            </DropdownMenu>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default TopNavbar;
