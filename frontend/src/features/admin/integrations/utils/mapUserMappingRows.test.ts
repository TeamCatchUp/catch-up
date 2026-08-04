import { describe, expect, it } from 'vitest';

import type { UserSourceMappingItem } from '../types/userSourceMappingApi';
import { mapUserMappingRow, toMappingCell } from './mapUserMappingRows';

const item = (overrides: Partial<UserSourceMappingItem> = {}): UserSourceMappingItem => ({
  user_id: 42,
  sub: 'sub-42',
  name: '직원20',
  email: 'yumi@catchup.io',
  atlassian: { name: 'yumi', identifier: 'yumi@catchup.io', picture: null },
  slack: { name: 'yumi', identifier: 'U012345', picture: 'https://img/slack.png' },
  github: { name: 'yumi-gh', identifier: 'yumi-gh', picture: null },
  confluence: null,
  channel_talk: { name: 'yumi', identifier: 'yumi@catchup.io', picture: null },
  ...overrides,
});

describe('toMappingCell', () => {
  it('null 응답은 미연동(null)이다', () => {
    expect(toMappingCell(null)).toBeNull();
  });

  it('name·identifier 둘 다 비면 계정 없음으로 본다', () => {
    expect(toMappingCell({ name: null, identifier: null, picture: 'https://img/x.png' })).toBeNull();
  });

  it('name만 없으면 "-" 폴백, identifier만 없으면 빈 문자열 폴백', () => {
    expect(toMappingCell({ name: null, identifier: 'id-1', picture: null })).toEqual({
      name: '-',
      identifier: 'id-1',
      picture: null,
    });
    expect(toMappingCell({ name: '유미', identifier: null, picture: null })).toEqual({
      name: '유미',
      identifier: '',
      picture: null,
    });
  });
});

describe('mapUserMappingRow', () => {
  it('4개 소스가 전부 있으면 fullyMapped다 (confluence는 atlassian에 합쳐져 무시)', () => {
    const row = mapUserMappingRow(item());
    expect(row.id).toBe('42');
    expect(row.user).toEqual({ name: '직원20' });
    expect(row.fullyMapped).toBe(true);
    expect(row.accounts.slack).toEqual({ name: 'yumi', identifier: 'U012345', picture: 'https://img/slack.png' });
  });

  it('하나라도 비면 fullyMapped가 아니다', () => {
    const row = mapUserMappingRow(item({ channel_talk: null }));
    expect(row.fullyMapped).toBe(false);
    expect(row.accounts.channel_talk).toBeNull();
  });

  it('빈 name·identifier 계정은 미연동으로 계산돼 fullyMapped를 깬다', () => {
    const row = mapUserMappingRow(item({ github: { name: null, identifier: null, picture: null } }));
    expect(row.fullyMapped).toBe(false);
  });
});
