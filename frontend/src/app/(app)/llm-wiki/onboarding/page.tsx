'use client';

import WikiOnboardingPage from '@/features/llm-wiki/components/onboarding/WikiOnboardingPage';
import { useWikiOnboardingAdminGuard } from '@/features/llm-wiki/hooks/useWikiOnboardingGate';

/**
 * 위키 생성 온보딩. 관리자만 채널을 만들 수 있어 그 밖의 사용자는 대시보드로 돌려보낸다.
 * 단계 이동은 useFunnel이 history에 쌓아 브라우저 뒤로가기가 이전 단계로 돌아간다.
 */
export default function Page() {
  const { blocked } = useWikiOnboardingAdminGuard();

  if (blocked) return null;

  return <WikiOnboardingPage />;
}
