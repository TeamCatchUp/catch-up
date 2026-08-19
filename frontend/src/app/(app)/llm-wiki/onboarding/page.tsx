'use client';

import { use } from 'react';

import WikiOnboardingPage from '@/features/llm-wiki/components/onboarding/WikiOnboardingPage';
import { useWikiOnboardingAdminGuard } from '@/features/llm-wiki/hooks/useWikiOnboardingGate';
import { resolveOnboardingStep } from '@/features/llm-wiki/utils/onboarding/resolveOnboardingStep';

interface PageProps {
  searchParams: Promise<{ step?: string }>;
}

/**
 * 위키 생성 온보딩. 관리자만 채널을 만들 수 있어 그 밖의 사용자는 대시보드로 돌려보낸다.
 * 단계를 URL에 두는 이유는 2단계에 진행·복귀 버튼이 시안에 없어서다 — 브라우저 뒤로가기가 그 자리를 대신한다.
 */
export default function Page({ searchParams }: PageProps) {
  const { step } = use(searchParams);
  const { blocked } = useWikiOnboardingAdminGuard();

  if (blocked) return null;

  return <WikiOnboardingPage step={resolveOnboardingStep(step)} />;
}
