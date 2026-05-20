'use client';

import { useCallback, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import AccountLogSection from '@/features/admin/audit-logs/components/sections/AccountLogSection';
import IntegrationLogSection from '@/features/admin/audit-logs/components/sections/IntegrationLogSection';
import QuestionLogSection from '@/features/admin/audit-logs/components/sections/QuestionLogSection';
import {
  AUDIT_TABS,
  type AuditTabSlug,
  DEFAULT_TAB_SLUG,
  fromTabSlug,
  toTabSlug,
} from '@/features/admin/audit-logs/constants/auditLogConfig';
import UnderlineTabs, { type UnderlineTabItem } from '@/shared/components/ui/underline-tabs';

const TAB_ITEMS: UnderlineTabItem<AuditTabSlug>[] = AUDIT_TABS.map((tab) => ({
  value: toTabSlug(tab),
  label: tab,
}));

/** 관리자 — 감사 로그 페이지 */
export default function AdminAuditLogsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // 로컬 state가 진실 공급원, URL은 사이드카. router.replace 직후 useSearchParams
  // 지연 반영으로 controlled Radix Tabs가 갇히던 케이스 회피.
  const urlSlug = toTabSlug(fromTabSlug(searchParams.get('tab') ?? DEFAULT_TAB_SLUG));
  const [activeSlug, setActiveSlugState] = useState<AuditTabSlug>(urlSlug);
  const [prevUrlSlug, setPrevUrlSlug] = useState<AuditTabSlug>(urlSlug);

  // 뒤로/앞으로·deep-link로 URL이 바뀌면 render 중 state 동기화
  if (urlSlug !== prevUrlSlug) {
    setPrevUrlSlug(urlSlug);
    setActiveSlugState(urlSlug);
  }

  const activeTab = fromTabSlug(activeSlug);

  const setActiveSlug = useCallback(
    (slug: AuditTabSlug) => {
      setActiveSlugState(slug);
      router.replace(`/admin/audit-logs?tab=${slug}`);
    },
    [router],
  );

  return (
    <section className="flex flex-col gap-5 px-16 pt-9 pb-25">
      {/* 헤더 */}
      <div className="flex flex-col gap-3">
        <h1 className="text-heading-xlarge text-content-normal">감사 로그</h1>

        {/* 밑줄 탭 */}
        <UnderlineTabs
          items={TAB_ITEMS}
          value={activeSlug}
          onValueChange={setActiveSlug}
          ariaLabel="감사 로그 탭"
          panelIdPrefix="audit-logs"
        />
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === '계정관리' && <AccountLogSection />}
      {activeTab === '질문' && <QuestionLogSection />}
      {activeTab === '연동' && <IntegrationLogSection />}
    </section>
  );
}
