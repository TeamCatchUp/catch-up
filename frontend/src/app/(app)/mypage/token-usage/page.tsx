'use client';

import MyTokenUsageSection from '@/features/admin/token-usage/components/sections/MyTokenUsageSection';

/** 마이페이지 — 나의 토큰 사용량 */
export default function MyTokenUsagePage() {
  return (
    <section className="flex flex-col gap-8 px-16 pt-9 pb-30">
      {/* 헤더 */}
      <div className="flex flex-col gap-6">
        <h1 className="text-heading-xlarge text-content-normal">토큰 사용량 관리</h1>
        <div className="flex items-center gap-6">
          <span className="text-heading-large border-content-normal text-content-normal border-b-2 pb-1.5">
            나의 토큰 사용량
          </span>
        </div>
      </div>

      {/* 콘텐츠 */}
      <MyTokenUsageSection />
    </section>
  );
}
