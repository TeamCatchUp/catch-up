'use client';

import { useState } from 'react';

import { OnboardingFunnel } from '@/features/onboarding';
import { WelcomeStep } from '@/features/onboarding/components/steps/WelcomeStep';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';

export default function OnboardingPage() {
  const { data, isLoading } = useCurrentUser(false);
  const [started, setStarted] = useState(false);

  // 버튼 클릭 후 + 로그인 완료 상태: funnel 시작
  if (started && data?.status === 'new') {
    return <OnboardingFunnel />;
  }

  // 항상 WelcomeStep을 먼저 표시
  return (
    <WelcomeStep
      isLoading={isLoading}
      onStart={() => {
        if (data?.status === 'new') {
          // 이미 로그인됨 → funnel로 전환
          setStarted(true);
        } else {
          // 비로그인 → SSO 통합로그인
          window.location.href = '/api/v1/auth/okta/login';
        }
      }}
    />
  );
}
