import WikiOnboardingPage from '@/features/llm-wiki/components/onboarding/WikiOnboardingPage';
import { resolveOnboardingStep } from '@/features/llm-wiki/utils/onboarding/resolveOnboardingStep';

interface PageProps {
  searchParams: Promise<{ step?: string }>;
}

/**
 * 위키 생성 온보딩. 생성 API가 없어 입력은 화면 상태로만 남는다.
 * 단계를 URL에 두는 이유는 2단계에 진행·복귀 버튼이 시안에 없어서다 — 브라우저 뒤로가기가 그 자리를 대신한다.
 */
export default async function Page({ searchParams }: PageProps) {
  const { step } = await searchParams;

  return <WikiOnboardingPage step={resolveOnboardingStep(step)} />;
}
