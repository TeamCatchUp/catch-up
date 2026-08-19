import { describe, expect, it } from 'vitest';

import type { AutomationCredentialItem } from '@/shared/types/automationApi';

import { mapChannelTalkChannel, mapOnboardingChannelRows } from './onboardingSourceMappers';

const credential = (overrides: Partial<AutomationCredentialItem> = {}): AutomationCredentialItem => ({
  connector: 'channel_talk',
  credential_id: 7,
  display_name: '고객지원',
  external_id: 'ct-1',
  external_name: '고객지원',
  is_configured: true,
  metadata: {},
  ...overrides,
});

describe('mapChannelTalkChannel', () => {
  it('credential_id를 그대로 싣는다 — 수집 설정 저장 경로의 키다', () => {
    expect(mapChannelTalkChannel(credential()).credentialId).toBe(7);
  });

  it('표시 이름은 display_name을 쓴다', () => {
    expect(mapChannelTalkChannel(credential({ display_name: '영업' })).name).toBe('영업');
  });

  it('webhook 미설정 채널도 목록에 실린다 — 구분은 isConfigured가 한다', () => {
    expect(mapChannelTalkChannel(credential({ is_configured: false })).isConfigured).toBe(false);
  });
});

describe('mapOnboardingChannelRows', () => {
  it('"최근 수정일"은 대응 필드가 없어 빈 문자열이다', () => {
    expect(mapOnboardingChannelRows([credential()])[0].lastModifiedLabel).toBe('');
  });

  it('연결이 없으면 빈 목록이다', () => {
    expect(mapOnboardingChannelRows([])).toEqual([]);
  });
});
