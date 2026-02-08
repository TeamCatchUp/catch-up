'use client';

import clsx from 'clsx';
import { usePathname, useRouter } from 'next/navigation';

import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';

export default function MypageLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const tabs = [
    { name: '프로필', href: '/mypage/settings' },
    { name: '협업툴 연동', href: '/mypage/integrations' },
    { name: '질문 히스토리', href: '/mypage/history' },
  ];

  return (
    <div className="flex flex-col">
      <TopNavbar pageType="mypage" />

      <div className="text-heading-large flex gap-6 bg-white pt-5 pl-16">
        {tabs.map((tab) => (
          <button
            key={tab.href}
            onClick={() => router.push(tab.href)}
            className={clsx(
              'cursor-pointer pb-2',
              pathname === tab.href ? 'border-gray-80 text-gray-80 border-b-[2px]' : 'text-gray-30',
            )}
          >
            {tab.name}
          </button>
        ))}
      </div>

      <main>{children}</main>
    </div>
  );
}
