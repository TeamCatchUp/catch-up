'use client';

import IntegrationsSection from '../member/sections/IntegrationsSection';

/**
 * 관리자 — 이용자 매핑 페이지.
 * 내용물은 구 레이아웃 그대로다. 신규 화면은 상태 감사 후 스펙 ②에서 다룬다.
 */
export default function UserMappingPageClient() {
  return (
    <section className="mx-auto flex w-full flex-col gap-6 px-16 pt-9 pb-30 min-[1440px]:max-w-287">
      <h1 className="text-heading-xlarge text-text-normal-normal">협업툴 연동</h1>
      <IntegrationsSection />
    </section>
  );
}
