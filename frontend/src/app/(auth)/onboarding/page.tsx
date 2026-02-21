'use client';

import { useState } from 'react';

import { OnboardingFunnel } from '@/features/onboarding';
import { WelcomeStep } from '@/features/onboarding/components/steps/WelcomeStep';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';

export default function OnboardingPage() {
  const { data, isError } = useCurrentUser(false);
  const [started, setStarted] = useState(false);

  if (started && data?.status === 'new') {
    return <OnboardingFunnel />;
  }

  return (
    <WelcomeStep
      onStart={() => {
        if (data?.status === 'new') {
          setStarted(true);
        } else if (!data || isError) {
          window.location.href = '/login';
        }
      }}
    />
  );
}
