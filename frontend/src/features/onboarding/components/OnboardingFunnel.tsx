'use client';

import { useFunnel } from '@use-funnel/browser';

import { useUserStore } from '@/shared/store/userStore';

import { useSubmitOrganization, useSubmitProfile } from '../mutations';
import type { OnboardingSteps } from '../types/onboarding';
import { CompleteStep } from './CompleteStep';
import { OnboardingLayout } from './OnboardingLayout';
import { ConnectorStep } from './steps/ConnectorStep';
import { OrgInfoStep } from './steps/OrgInfoStep';
import { ProfileStep } from './steps/ProfileStep';
import { WelcomeStep } from './steps/WelcomeStep';

export function OnboardingFunnel() {
  const user = useUserStore((s) => s.user);
  const isAdmin = user?.role === 'ROOT_ADMIN';

  const submitProfile = useSubmitProfile();
  const submitOrg = useSubmitOrganization();

  const funnel = useFunnel<OnboardingSteps>({
    id: 'onboarding',
    initial: { step: 'Welcome', context: {} },
  });

  if (funnel.step === 'Welcome') {
    return (
      <funnel.Render
        Welcome={({ history }) => (
          <WelcomeStep onStart={() => history.push('Profile', {})} />
        )}
        Profile={() => null}
        OrgInfo={() => null}
        Connector={() => null}
        Complete={() => null}
      />
    );
  }

  return (
    <OnboardingLayout>
      <funnel.Render
        Welcome={() => null}
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
              submitProfile.mutate(data);
              history.replace('Profile', data);
              if (isAdmin) {
                history.push('OrgInfo', data);
              } else {
                history.push('Connector', data);
              }
            }}
            onBack={() => history.back()}
          />
        )}
        OrgInfo={({ context, history }) => (
          <OrgInfoStep
            defaultValues={{
              company_name: context.company_name ?? '',
              team_size: context.team_size ?? '',
            }}
            onSubmit={(orgData) => {
              submitOrg.mutate(orgData);
              history.replace('OrgInfo', { ...context, ...orgData });
              history.push('Complete', { ...context, ...orgData });
            }}
            onBack={() => history.back()}
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
            onBack={() => history.back()}
          />
        )}
        Complete={({ context }) => (
          <CompleteStep data={context} isAdmin={isAdmin} />
        )}
      />
    </OnboardingLayout>
  );
}
