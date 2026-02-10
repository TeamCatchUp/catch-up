'use client';

import { useCallback,useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { Button } from '@/shared/components/ui/button';
import { authQueries } from '@/shared/queries/auth.queries';

import { useCompleteOnboarding } from '../mutations';
import type { OnboardingSteps } from '../types/onboarding';

interface CompleteStepProps {
  data: OnboardingSteps['Complete'];
  isAdmin: boolean;
}

export function CompleteStep({ data, isAdmin }: CompleteStepProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { mutate: complete, isPending, isError } = useCompleteOnboarding();

  const submitOnboarding = useCallback(() => {
    complete(
      {
        name: data.name,
        position: data.position,
        rank: data.rank,
        department: data.department,
        company_name: data.company_name,
        team_size: data.team_size,
        connectors: {
          jira_account_id: data.jira_account_id,
          github_account_id: data.github_account_id,
          slack_account_id: data.slack_account_id,
        },
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({ queryKey: authQueries.all() });
          if (isAdmin) {
            router.replace('/');
          } else {
            router.replace('/pending');
          }
        },
      },
    );
  }, [complete, data, isAdmin, queryClient, router]);

  useEffect(() => {
    submitOnboarding();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex size-full items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center">
        {isPending && (
          <>
            <div className="text-display-large tracking-tight text-gray-80">
              온보딩을 완료하고 있습니다...
            </div>
            <p className="text-body-large tracking-tight text-gray-50">잠시만 기다려 주세요.</p>
          </>
        )}
        {isError && (
          <>
            <div className="text-display-large tracking-tight text-gray-80">
              온보딩 완료에 실패했습니다.
            </div>
            <p className="text-body-large tracking-tight text-gray-50">
              네트워크 상태를 확인하고 다시 시도해주세요.
            </p>
            <Button
              variant="box-solid-primary"
              size="lg"
              className="mt-4 h-[46px]"
              onClick={submitOnboarding}
            >
              다시 시도
            </Button>
          </>
        )}
        {!isPending && !isError && (
          <>
            <div className="text-display-large tracking-tight text-gray-80">완료!</div>
            <p className="text-body-large tracking-tight text-gray-50">잠시만 기다려 주세요.</p>
          </>
        )}
      </div>
    </div>
  );
}
