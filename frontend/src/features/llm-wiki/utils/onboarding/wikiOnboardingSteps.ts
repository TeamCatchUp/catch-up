/** 온보딩 입력 스냅샷. 스텝을 넘길 때 funnel context로 실려 새로고침 뒤에도 남는다 */
export interface WikiOnboardingDraft {
  name: string;
  categoryId: string | null;
  purposeId: string | null;
  docKindId: string | null;
  toneId: string | null;
  scheduleSelection: Record<string, string>;
  selectedCredentialIds: readonly number[];
}

/** useFunnel 스텝별 context 타입. 세 스텝이 같은 스냅샷을 이어받는다 */
export type WikiOnboardingSteps = {
  purpose: Partial<WikiOnboardingDraft>;
  source: Partial<WikiOnboardingDraft>;
  complete: Partial<WikiOnboardingDraft>;
};

export const WIKI_ONBOARDING_FUNNEL_ID = 'wiki-onboarding';
