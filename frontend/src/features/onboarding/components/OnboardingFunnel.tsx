'use client';

import { useRef } from 'react';
import { useFunnel } from '@use-funnel/browser';

import { useUserStore } from '@/shared/store/userStore';

import type { OnboardingSteps, OrgInfoFormData } from '../types/onboardingModel';
import { CompleteStep } from './CompleteStep';
import { OnboardingLayout } from './OnboardingLayout';
import { OrgInfoStep } from './steps/OrgInfoStep';
import { ProfileStep } from './steps/ProfileStep';

export function OnboardingFunnel() {
  const user = useUserStore((s) => s.user);
  const isAdmin = user?.role === 'admin';

  // 뒤로가기 후 다시 앞으로 갈 때 입력값 보존을 위한 캐시
  const cachedOrgInfo = useRef<Partial<OrgInfoFormData>>({});

  const funnel = useFunnel<OnboardingSteps>({
    id: 'onboarding',
    initial: { step: 'Profile', context: {} },
  });

  return (
    <OnboardingLayout>
      <funnel.Render
        Profile={({ context, history }) => (
          <ProfileStep
            isAdmin={isAdmin}
            defaultValues={{
              name: context.name ?? user?.name ?? '',
              job_level: context.job_level ?? '',
              department: context.department ?? '',
            }}
            onSubmit={(data) => {
              history.replace('Profile', data);
              if (isAdmin) {
                history.push('OrgInfo', { ...data, ...cachedOrgInfo.current });
              } else {
                history.push('Complete', data);
              }
            }}
          />
        )}
        OrgInfo={({ context, history }) => (
          <OrgInfoStep
            defaultValues={{
              company_name: context.company_name ?? '',
              company_size: context.company_size ?? '',
            }}
            onSubmit={(orgData) => {
              history.replace('OrgInfo', { ...context, ...orgData });
              history.push('Complete', { ...context, ...orgData });
            }}
            onBack={(orgData) => {
              cachedOrgInfo.current = orgData;
              history.back();
            }}
          />
        )}
        Complete={({ context }) => <CompleteStep data={context} isAdmin={isAdmin} />}
      />
    </OnboardingLayout>
  );
}
