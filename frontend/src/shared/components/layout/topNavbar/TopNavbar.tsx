'use client';

import { useState } from 'react';
import Link from 'next/link';

import MoreButtonModal from './MoreButtonModal';
import ShareButtonModal from './ShareButtonModal';

import Settings from '/public/icons/icon/admin_panel_settings.svg';
import Home from '/public/icons/icon/home.svg';
import Kebeb_2 from '/public/icons/icon/kebeb 2.svg';
import MyPage from '/public/icons/icon/person.svg';

type PageType = 'home' | 'mypage' | 'settings';

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
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [isMoreModalOpen, setIsMoreModalOpen] = useState(false);

  const config = pageConfigs[pageType];
  const IconComponent = config.icon;

  const toggleShareModal = () => {
    setIsShareModalOpen((prev) => !prev);
    setIsMoreModalOpen(false);
  };

  const toggleMoreModal = () => {
    setIsMoreModalOpen((prev) => !prev);
    setIsShareModalOpen(false);
  };

  return (
    <nav aria-label="메인 네비게이션" className="border-neutral-3 sticky top-0 z-50 h-full w-full border-b bg-white">
      <div className="flex justify-between px-16 py-2">
        <div className="flex items-center justify-center">
          <Link href={config.href}>
            <button className="text-gray-80 flex cursor-pointer gap-2">
              <IconComponent className="h-6 w-6" />
              <span className="text-heading-medium relative top-[0.5px]">{config.label}</span>
            </button>
          </Link>
        </div>
        <ul className="flex items-center justify-center gap-2">
          <li className="relative">
            <button
              onClick={toggleShareModal}
              aria-expanded={isShareModalOpen}
              aria-controls="share-modal"
              className={`flex h-[38.5px] cursor-pointer items-center justify-center rounded-lg border px-2.5 py-1.5 text-center transition-colors ${
                isShareModalOpen
                  ? 'border-neutral-4 bg-neutral-2 active:border-neutral-5 active:bg-neutral-3'
                  : 'border-neutral-3 active:border-neutral-5 active:bg-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 bg-white'
              } `}
            >
              <span className="text-body-small text-gray-70 relative top-px flex items-center">공유</span>
            </button>
            {/* 공유 모달 */}
            {isShareModalOpen && (
              <div className="absolute top-full right-0 mt-1.5">
                <ShareButtonModal onClose={() => setIsShareModalOpen(false)} />
              </div>
            )}
          </li>
          <li className="relative">
            <button
              aria-expanded={isMoreModalOpen}
              aria-controls="more-modal"
              onClick={toggleMoreModal}
              className={`${
                isMoreModalOpen
                  ? 'border-neutral-4 bg-neutral-2 active:border-neutral-5 active:bg-neutral-3'
                  : 'border-neutral-3 active:border-neutral-5 active:bg-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 bg-white'
              } cursor-pointer rounded-lg border px-1.5 py-1.5 transition-colors`}
            >
              <Kebeb_2 className="text-gray-70 h-6 w-6" />
            </button>
            {/* 더보기 모달 */}
            {isMoreModalOpen && (
              <div className="absolute top-full right-0 mt-1.5">
                <MoreButtonModal onClose={() => setIsMoreModalOpen(false)} />
              </div>
            )}
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default TopNavbar;
