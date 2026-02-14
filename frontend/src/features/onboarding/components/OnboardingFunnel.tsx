'use client';

import { useRef } from 'react';
import { useFunnel } from '@use-funnel/browser';

import { useUserStore } from '@/shared/store/userStore';

import type { ConnectorFormData, OnboardingSteps, OrgInfoFormData } from '../types/onboarding';
import { CompleteStep } from './CompleteStep';
import { OnboardingLayout } from './OnboardingLayout';
import { ConnectorStep } from './steps/ConnectorStep';
import { OrgInfoStep } from './steps/OrgInfoStep';
import { ProfileStep } from './steps/ProfileStep';

export function OnboardingFunnel() {
  const user = useUserStore((s) => s.user);
  const isAdmin = user?.role === 'admin';

  // 뒤로가기 후 다시 앞으로 갈 때 입력값 보존을 위한 캐시
  const cachedOrgInfo = useRef<Partial<OrgInfoFormData>>({});
  const cachedConnector = useRef<Partial<ConnectorFormData>>({});

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
              position: context.position ?? '',
              rank: context.rank ?? '',
              department: context.department ?? '',
            }}
            onSubmit={(data) => {
              history.replace('Profile', data);
              if (isAdmin) {
                history.push('OrgInfo', { ...data, ...cachedOrgInfo.current });
              } else {
                history.push('Connector', { ...data, ...cachedConnector.current });
              }
            }}
          />
        )}
        OrgInfo={({ context, history }) => (
          <OrgInfoStep
            defaultValues={{
              company_name: context.company_name ?? '',
              team_size: context.team_size ?? '',
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
        Connector={({ context, history }) => (
          <ConnectorStep
            defaultValues={{
              jira_account_id: context.jira_account_id ?? '',
              github_account_id: context.github_account_id ?? '',
              slack_account_id: context.slack_account_id ?? '',
            }}
            onSubmit={(connData) => {
              history.replace('Connector', { ...context, ...connData });
              history.push('Complete', { ...context, ...connData });
            }}
            onBack={(connData) => {
              cachedConnector.current = connData;
              history.back();
            }}
          />
        )}
        Complete={({ context }) => <CompleteStep data={context} isAdmin={isAdmin} />}
      />
    </OnboardingLayout>
  );
}
