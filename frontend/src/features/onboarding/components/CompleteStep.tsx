'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { Button } from '@/shared/components/ui/button';
import { authQueries } from '@/shared/queries/auth.queries';

import { useAdminSignUp, useUserSignUp } from '../mutations';
import type { OnboardingSteps } from '../types/onboarding';

interface CompleteStepProps {
  data: OnboardingSteps['Complete'];
  isAdmin: boolean;
}

export function CompleteStep({ data, isAdmin }: CompleteStepProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const userSignUp = useUserSignUp();
  const adminSignUp = useAdminSignUp();

  const { isPending, isError } = isAdmin ? adminSignUp : userSignUp;
  const hasSubmitted = useRef(false);

  const submitOnboarding = useCallback(() => {
    const onSuccess = async () => {
      await queryClient.invalidateQueries({ queryKey: authQueries.all() });
      router.replace('/');
    };

    if (isAdmin) {
      adminSignUp.mutate(
        {
          name: data.name,
          job_level: data.job_level,
          company_name: data.company_name!,
          company_size: data.company_size!,
          workspace_name: 'main',
        },
        { onSuccess },
      );
    } else {
      userSignUp.mutate(
        {
          name: data.name,
          job_level: data.job_level,
          department: data.department!,
        },
        { onSuccess },
      );
    }
  }, [adminSignUp, userSignUp, data, isAdmin, queryClient, router]);

  useEffect(() => {
    if (hasSubmitted.current) return;
    hasSubmitted.current = true;
    submitOnboarding();
  }, [submitOnboarding]);

  return (
    <div className="flex size-full items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center">
        {isPending && (
          <>
            <div className="text-display-large text-content-normal tracking-tight">온보딩을 완료하고 있습니다...</div>
            <p className="text-body-large text-content-alternative tracking-tight">잠시만 기다려 주세요.</p>
          </>
        )}
        {isError && (
          <>
            <div className="text-display-large text-content-normal tracking-tight">온보딩 완료에 실패했습니다.</div>
            <p className="text-body-large text-content-alternative tracking-tight">
              네트워크 상태를 확인하고 다시 시도해주세요.
            </p>
            <Button variant="box-solid-primary" size="lg" className="mt-4 h-[46px]" onClick={submitOnboarding}>
              다시 시도
            </Button>
          </>
        )}
        {!isPending && !isError && (
          <>
            <div className="text-display-large text-content-normal tracking-tight">완료!</div>
            <p className="text-body-large text-content-alternative tracking-tight">잠시만 기다려 주세요.</p>
          </>
        )}
      </div>
    </div>
  );
}
