import { describe, expect, it } from 'vitest';

import { resolveOnboardingStep } from './resolveOnboardingStep';

describe('resolveOnboardingStep', () => {
  it('파라미터가 없으면 첫 단계로 시작한다', () => {
    expect(resolveOnboardingStep(undefined)).toBe(1);
  });

  it('step=2는 수집 위치 단계다', () => {
    expect(resolveOnboardingStep('2')).toBe(2);
  });

  // 8/14 시안 갱신으로 완료 화면이 도착해 3이 유효 단계가 됐다
  it('step=3은 확인 및 완료 단계다', () => {
    expect(resolveOnboardingStep('3')).toBe(3);
  });

  it('해석할 수 없는 값은 첫 단계로 떨어진다', () => {
    expect(resolveOnboardingStep('abc')).toBe(1);
    expect(resolveOnboardingStep('')).toBe(1);
    expect(resolveOnboardingStep('-1')).toBe(1);
    expect(resolveOnboardingStep('4')).toBe(1);
  });
});
