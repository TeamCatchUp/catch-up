/** 화면이 있는 단계. 3단계(완료)는 시안이 없어 여기 없다 */
export type OnboardingStepNumber = 1 | 2;

/**
 * URL의 step 파라미터를 화면 단계로 옮긴다.
 * 아는 값이 아니면 1로 떨어뜨린다 — 없는 단계를 요청받고 빈 화면을 내주지 않기 위해서다.
 */
export function resolveOnboardingStep(step: string | undefined): OnboardingStepNumber {
  return step === '2' ? 2 : 1;
}
