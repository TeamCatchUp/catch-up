'use client';

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
import { useTabRouting } from '@/shared/hooks/useTabRouting';

const TAB_ITEMS: UnderlineTabItem<AuditTabSlug>[] = AUDIT_TABS.map((tab) => ({
  value: toTabSlug(tab),
  label: tab,
}));

/** 관리자 — 감사 로그 페이지 */
export default function AdminAuditLogsPage() {
  const [activeSlug, setActiveSlug] = useTabRouting<AuditTabSlug>((raw) =>
    toTabSlug(fromTabSlug(raw ?? DEFAULT_TAB_SLUG)),
  );
  const activeTab = fromTabSlug(activeSlug);

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
