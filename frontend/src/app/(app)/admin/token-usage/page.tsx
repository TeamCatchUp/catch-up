'use client';

import { type KeyboardEvent, useCallback, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import LimitReleaseSection from '@/features/admin/token-usage/components/sections/LimitReleaseSection';
import MyTokenUsageSection from '@/features/admin/token-usage/components/sections/MyTokenUsageSection';
import OrgTokenUsageSection from '@/features/admin/token-usage/components/sections/OrgTokenUsageSection';
import UserManagementSection from '@/features/admin/token-usage/components/sections/UserManagementSection';
import {
  DEFAULT_TAB_SLUG,
  fromTabSlug,
  TOKEN_USAGE_TABS,
  type TokenUsageTab,
  toTabSlug,
} from '@/features/admin/token-usage/constants/tokenUsageConfig';
import { cn } from '@/shared/utils/cn';

/** 관리자 — 토큰 사용량 관리 페이지 */
export default function AdminTokenUsagePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = fromTabSlug(searchParams.get('tab') ?? DEFAULT_TAB_SLUG);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const setActiveTab = useCallback(
    (tab: TokenUsageTab) => {
      const slug = toTabSlug(tab);
      router.replace(`/admin/token-usage?tab=${slug}`);
    },
    [router],
  );

  const handleTabKeyDown = (e: KeyboardEvent, index: number) => {
    let newIndex = index;

    switch (e.key) {
      case 'ArrowLeft':
        newIndex = index === 0 ? TOKEN_USAGE_TABS.length - 1 : index - 1;
        break;
      case 'ArrowRight':
        newIndex = index === TOKEN_USAGE_TABS.length - 1 ? 0 : index + 1;
        break;
      case 'Home':
        newIndex = 0;
        break;
      case 'End':
        newIndex = TOKEN_USAGE_TABS.length - 1;
        break;
      default:
        return;
    }

    e.preventDefault();
    setActiveTab(TOKEN_USAGE_TABS[newIndex]);
    tabRefs.current[newIndex]?.focus();
  };

  const activeSlug = toTabSlug(activeTab);

  return (
    <section className="flex flex-col gap-8 px-16 pt-9 pb-30">
      {/* 헤더 */}
      <div className="flex flex-col gap-6">
        <h1 className="text-heading-xlarge text-content-normal">토큰 사용량 관리</h1>

        {/* 밑줄 탭 */}
        <div role="tablist" aria-label="토큰 사용량 관리 탭" className="flex items-center gap-6">
          {TOKEN_USAGE_TABS.map((tab, index) => {
            const isActive = activeTab === tab;
            const slug = toTabSlug(tab);
            return (
              <button
                key={tab}
                ref={(el) => {
                  tabRefs.current[index] = el;
                }}
                role="tab"
                id={`tab-${slug}`}
                aria-selected={isActive}
                aria-controls={`tabpanel-${slug}`}
                tabIndex={isActive ? 0 : -1}
                type="button"
                onClick={() => setActiveTab(tab)}
                onKeyDown={(e) => handleTabKeyDown(e, index)}
                className={cn(
                  'text-heading-large cursor-pointer pb-1.5',
                  isActive ? 'border-content-normal text-content-normal border-b-2' : 'text-content-assistive',
                )}
              >
                {tab}
              </button>
            );
          })}
        </div>
      </div>

      {/* 탭 콘텐츠 */}
      <div role="tabpanel" id={`tabpanel-${activeSlug}`} aria-labelledby={`tab-${activeSlug}`} tabIndex={0}>
        {activeTab === '나의 토큰 사용량' ? (
          <MyTokenUsageSection />
        ) : activeTab === '조직 토큰 사용량' ? (
          <OrgTokenUsageSection />
        ) : activeTab === '이용자 관리' ? (
          <UserManagementSection />
        ) : activeTab === '제한 해제 요청' ? (
          <LimitReleaseSection />
        ) : null}
      </div>
    </section>
  );
}
