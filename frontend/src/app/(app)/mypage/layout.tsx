'use client';

import { usePathname, useRouter } from 'next/navigation';

import { cn } from '@/shared/utils/cn';

/**
 * 마이페이지 하위 탭 전환을 담당하는 레이아웃
 * 현재 경로를 기준으로 활성 탭 스타일을 적용
 */
export default function MypageLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const tabs = [
    { name: '프로필', href: '/mypage/profile' },
    { name: '협업툴 연동', href: '/mypage/integrations' },
    { name: '질문 히스토리', href: '/mypage/history' },
    { name: '도움말', href: '/mypage/help' },
  ];

  return (
    <div className="flex flex-col">
      <div className="text-heading-large flex gap-6 bg-white pl-16 pt-5">
        {tabs.map((tab) => (
          <button
            key={tab.href}
            onClick={() => router.push(tab.href)}
            className={cn(
              'cursor-pointer pb-2',
              pathname === tab.href ? 'border-b-[2px] border-gray-80 text-gray-80' : 'text-gray-30',
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
