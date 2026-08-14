/** 화면이 있는 단계. 8/14 시안 갱신으로 완료(3)가 추가됐다 */
export type OnboardingStepNumber = 1 | 2 | 3;

/**
 * URL의 step 파라미터를 화면 단계로 옮긴다.
 * 아는 값이 아니면 1로 떨어뜨린다 — 없는 단계를 요청받고 빈 화면을 내주지 않기 위해서다.
 */
export function resolveOnboardingStep(step: string | undefined): OnboardingStepNumber {
  if (step === '2') return 2;
  if (step === '3') return 3;
  return 1;
}
