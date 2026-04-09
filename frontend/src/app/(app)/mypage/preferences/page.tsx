'use client';

import DisplayModeSection from '@/features/mypage/preferences/components/sections/DisplayModeSection';
import PromptBuilderSection from '@/features/mypage/preferences/components/sections/PromptBuilderSection';

export default function PreferencesPage() {
  return (
    <section className="flex min-w-150 flex-col gap-12 px-16 pt-9 pb-30">
      <h1 className="text-heading-xlarge text-content-normal">개인 맞춤 설정</h1>
      <div className="flex flex-col gap-12">
        <PromptBuilderSection />
        <DisplayModeSection />
      </div>
    </section>
  );
}
