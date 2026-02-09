'use client';

import { OnboardingFunnel } from '@/features/onboarding';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';

export default function OnboardingPage() {
  const { isLoading } = useCurrentUser(true);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-xl font-semibold">로딩 중...</div>
      </div>
    );
  }

  return <OnboardingFunnel />;
}
