import { describe, expect, it } from 'vitest';

import { shouldStartWikiOnboarding } from './useWikiOnboardingGate';

describe('shouldStartWikiOnboarding', () => {
  it('채널이 없는 관리자는 생성 화면으로 간다', () => {
    expect(shouldStartWikiOnboarding('admin', 0)).toBe(true);
  });

  it('채널이 하나라도 있으면 대시보드에 남는다', () => {
    expect(shouldStartWikiOnboarding('admin', 1)).toBe(false);
  });

  it('일반 사용자는 채널이 없어도 보내지 않는다 — 온보딩을 끝낼 수 없다', () => {
    expect(shouldStartWikiOnboarding('user', 0)).toBe(false);
  });

  it('응답이 아직 없으면 판정하지 않는다', () => {
    expect(shouldStartWikiOnboarding(undefined, 0)).toBe(false);
    expect(shouldStartWikiOnboarding('admin', undefined)).toBe(false);
    expect(shouldStartWikiOnboarding(undefined, undefined)).toBe(false);
  });
});
