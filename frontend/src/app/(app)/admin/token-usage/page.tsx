'use client';

import LimitReleaseSection from '@/features/admin/token-usage/components/sections/LimitReleaseSection';
import MyTokenUsageSection from '@/features/admin/token-usage/components/sections/MyTokenUsageSection';
import OrgTokenUsageSection from '@/features/admin/token-usage/components/sections/OrgTokenUsageSection';
import UserManagementSection from '@/features/admin/token-usage/components/sections/UserManagementSection';
import {
  DEFAULT_TAB_SLUG,
  fromTabSlug,
  TOKEN_USAGE_TABS,
  type TokenUsageTabSlug,
  toTabSlug,
} from '@/features/admin/token-usage/constants/tokenUsageConfig';
import UnderlineTabs, { type UnderlineTabItem } from '@/shared/components/ui/underline-tabs';
import { useTabRouting } from '@/shared/hooks/useTabRouting';

const TAB_ITEMS: UnderlineTabItem<TokenUsageTabSlug>[] = TOKEN_USAGE_TABS.map((tab) => ({
  value: toTabSlug(tab),
  label: tab,
}));

/** 관리자 — 토큰 사용량 관리 페이지 */
export default function AdminTokenUsagePage() {
  const [activeSlug, setActiveSlug] = useTabRouting<TokenUsageTabSlug>((raw) =>
    toTabSlug(fromTabSlug(raw ?? DEFAULT_TAB_SLUG)),
  );
  const activeTab = fromTabSlug(activeSlug);

  return (
    <section className="flex flex-col gap-8 px-16 pt-9 pb-30">
      {/* 헤더 */}
      <div className="flex flex-col gap-6">
        <h1 className="text-heading-xlarge text-text-normal-normal">토큰 사용량 관리</h1>

        {/* 밑줄 탭 */}
        <UnderlineTabs
          items={TAB_ITEMS}
          value={activeSlug}
          onValueChange={setActiveSlug}
          ariaLabel="토큰 사용량 관리 탭"
          panelIdPrefix="token-usage"
        />
      </div>

      {/* 탭 콘텐츠 */}
      <div
        role="tabpanel"
        id={`tabpanel-token-usage-${activeSlug}`}
        aria-labelledby={`tab-token-usage-${activeSlug}`}
        tabIndex={0}
      >
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
