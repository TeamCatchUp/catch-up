'use client';

import Link from 'next/link';

import Settings from '@/public/icons/icon/admin_panel_settings.svg';
import AI from '@/public/icons/icon/ai.svg';
import Home from '@/public/icons/icon/home.svg';
import Kebab2 from '@/public/icons/icon/kebeb 2.svg';
import MyPage from '@/public/icons/icon/person.svg';
import { Button } from '@/shared/components/ui/button';
import { DropdownMenu, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';

import { MoreButtonContent } from './MoreButtonModal';

type PageType = 'home' | 'search' | 'mypage' | 'settings';

interface PageConfig {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href: string;
}

/**
 * 상단 네비게이션의 페이지 타입별 아이콘/라벨/링크를 정의
 */
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
    href: '/mypage/profile',
  },
  settings: {
    icon: Settings,
    label: '권한 설정',
    href: '/admin/organization',
  },
};

interface TopNavbarProps {
  pageType: PageType;
}

/**
 * 화면 타입에 맞는 상단 네비게이션을 렌더링한다.
 */
export default function TopNavbar({ pageType }: TopNavbarProps) {
  const config = pageConfigs[pageType];
  const IconComponent = config.icon;

  return (
    <nav
      aria-label="메인 네비게이션"
      className="border-edge-neutral bg-fill-normal z-header sticky top-0 w-full border-b"
    >
      <div className="flex justify-between px-16 py-2">
        <div className="flex items-center justify-center">
          <Link href={config.href} className="text-content-normal flex cursor-pointer gap-2">
            <IconComponent className="h-6 w-6" />
            <span className="text-heading-medium relative top-[0.5px]">{config.label}</span>
          </Link>
        </div>
        <ul className="flex items-center justify-center gap-2">
          <li>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="icon-only-gray" size="md">
                  <Kebab2 className="h-6 w-6" />
                </Button>
              </DropdownMenuTrigger>
              <MoreButtonContent />
            </DropdownMenu>
          </li>
        </ul>
      </div>
    </nav>
  );
}
