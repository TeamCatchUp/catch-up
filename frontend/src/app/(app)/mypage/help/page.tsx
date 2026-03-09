'use client';

import AccountSupportSection from '@/features/mypage/help/components/AccountSupportSection';
import ContactChannelSection from '@/features/mypage/help/components/ContactChannelSection';
import GuideTutorialSection from '@/features/mypage/help/components/GuideTutorialSection';
import TermsPolicySection from '@/features/mypage/help/components/TermsPolicySection';
import { Separator } from '@/shared/components/ui/separator';

export default function MypageHelpPage() {
  return (
    <section className="mx-auto flex w-282 shrink-0 flex-col gap-6 px-16 pt-9 pb-[120px]">
      <h1 className="text-heading-xlarge text-content-normal">도움말</h1>
      <Separator />
      <div className="flex flex-col gap-12">
        <GuideTutorialSection />
        <AccountSupportSection />
        <TermsPolicySection />
        <ContactChannelSection />
      </div>
    </section>
  );
}
