'use client';

import { useState } from 'react';

import AccountLogSection from '@/features/admin/audit-logs/components/sections/AccountLogSection';
import QuestionLogSection from '@/features/admin/audit-logs/components/sections/QuestionLogSection';
import { AUDIT_TABS, type AuditTab } from '@/features/admin/audit-logs/constants/auditLogConfig';
import { cn } from '@/shared/utils/cn';

/** 관리자 — 감사 로그 페이지 */
export default function AdminAuditLogsPage() {
  const [activeTab, setActiveTab] = useState<AuditTab>('질문');

  return (
    <section className="flex flex-col gap-5 px-16 pt-9 pb-25">
      {/* 헤더 */}
      <div className="flex flex-col gap-3">
        <h1 className="text-heading-xlarge text-gray-80">감사 로그</h1>

        {/* 밑줄 탭 */}
        <div className="flex items-center gap-6">
          {AUDIT_TABS.map((tab) => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={cn(
                  'text-heading-large cursor-pointer pb-1.5',
                  isActive ? 'border-gray-80 text-gray-80 border-b-2' : 'text-gray-30',
                )}
              >
                {tab}
              </button>
            );
          })}
        </div>
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === '계정관리' && <AccountLogSection />}
      {activeTab === '질문' && <QuestionLogSection />}
      {activeTab === '연동' && (
        <div className="text-body-small flex h-80 items-center justify-center text-gray-50">
          연동 로그 기능은 준비 중입니다.
        </div>
      )}
    </section>
  );
}
