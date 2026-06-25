'use client';

import AccountSupportSection from '@/features/mypage/help/components/main/AccountSupportSection';
import CatchUpMcpSection from '@/features/mypage/help/components/main/CatchUpMcpSection';
import ContactChannelSection from '@/features/mypage/help/components/main/ContactChannelSection';
import GuideTutorialSection from '@/features/mypage/help/components/main/GuideTutorialSection';
import TermsPolicySection from '@/features/mypage/help/components/main/TermsPolicySection';
import { Separator } from '@/shared/components/ui/separator';

export default function MypageHelpPage() {
  return (
    <section className="flex w-full flex-col px-6 pt-9 pb-30 lg:px-16">
      <div className="mx-auto flex w-full max-w-[1040px] flex-col gap-6">
        <h1 className="text-heading-xlarge text-text-normal-normal">도움말</h1>
        <Separator />
        <div className="flex flex-col gap-12">
          <CatchUpMcpSection />
          <GuideTutorialSection />
          <AccountSupportSection />
          <TermsPolicySection />
          <ContactChannelSection />
        </div>
      </div>
    </section>
  );
}
