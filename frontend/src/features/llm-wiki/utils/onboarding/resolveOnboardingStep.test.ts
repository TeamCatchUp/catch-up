import { describe, expect, it } from 'vitest';

import { resolveOnboardingStep } from './resolveOnboardingStep';

describe('resolveOnboardingStep', () => {
  it('파라미터가 없으면 첫 단계로 시작한다', () => {
    expect(resolveOnboardingStep(undefined)).toBe(1);
  });

  it('step=2는 수집 위치 단계다', () => {
    expect(resolveOnboardingStep('2')).toBe(2);
  });

  // 완료 화면이 시안에 없다. 3을 2나 빈 화면으로 흘려보내면 그 부재가 코드에서 사라진다
  it('완료 단계(3)는 화면이 없어 첫 단계로 떨어진다', () => {
    expect(resolveOnboardingStep('3')).toBe(1);
  });

  it('해석할 수 없는 값은 첫 단계로 떨어진다', () => {
    expect(resolveOnboardingStep('abc')).toBe(1);
    expect(resolveOnboardingStep('')).toBe(1);
    expect(resolveOnboardingStep('-1')).toBe(1);
  });
});
