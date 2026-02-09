'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useCompleteOnboarding } from '../mutations';
import type { OnboardingSteps } from '../types/onboarding';

interface CompleteStepProps {
  data: OnboardingSteps['Complete'];
  isAdmin: boolean;
}

export function CompleteStep({ data, isAdmin }: CompleteStepProps) {
  const router = useRouter();
  const { mutate: complete, isPending } = useCompleteOnboarding();

  useEffect(() => {
    complete(
      {
        connectors: {
          jira_account_id: data.jira_account_id,
          github_account_id: data.github_account_id,
          slack_account_id: data.slack_account_id,
        },
      },
      {
        onSuccess: () => {
          if (isAdmin) {
            router.replace('/');
          } else {
            router.replace('/pending');
          }
        },
      },
    );
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex size-full items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="text-display-large tracking-tight text-gray-80">
          {isPending ? '온보딩을 완료하고 있습니다...' : '완료!'}
        </div>
        <p className="text-body-large tracking-tight text-gray-50">잠시만 기다려 주세요.</p>
      </div>
    </div>
  );
}
