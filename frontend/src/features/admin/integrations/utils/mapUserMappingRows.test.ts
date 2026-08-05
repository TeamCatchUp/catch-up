import { describe, expect, it } from 'vitest';

import type { MappingStatusResponse, UserSourceMappingItem } from '../types/userSourceMappingApi';
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

const counts = (overrides: Partial<MappingStatusResponse> = {}): MappingStatusResponse => ({
  jira: { users: 10, mapped: 5 },
  confluence: { users: 10, mapped: 0 },
  slack: { users: 10, mapped: 5 },
  github: { users: 10, mapped: 5 },
  channel_talk: { users: 10, mapped: 2 },
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

describe('mapUserMappingRow — 미사용 추론 (develop 로직 이관)', () => {
  it('서비스에 매핑이 운영 중인데 이 사용자만 없으면 미사용이다', () => {
    const row = mapUserMappingRow(item({ github: null }), counts());
    expect(row.accounts.github).toBe('unused');
  });

  it('서비스 전체가 0건이면 미연동(null)이다', () => {
    const row = mapUserMappingRow(item({ github: null }), counts({ github: { users: 10, mapped: 0 } }));
    expect(row.accounts.github).toBeNull();
  });

  it('atlassian 열은 Jira와 Confluence 카운트를 합쳐 판단한다', () => {
    const jiraOnly = counts({ jira: { users: 10, mapped: 0 }, confluence: { users: 10, mapped: 3 } });
    expect(mapUserMappingRow(item({ atlassian: null }), jiraOnly).accounts.atlassian).toBe('unused');

    const none = counts({ jira: { users: 10, mapped: 0 }, confluence: { users: 10, mapped: 0 } });
    expect(mapUserMappingRow(item({ atlassian: null }), none).accounts.atlassian).toBeNull();
  });

  it('채널톡은 미등록 개념이 없다 — 미매핑은 항상 미사용', () => {
    const row = mapUserMappingRow(item({ channel_talk: null }), counts());
    expect(row.accounts.channel_talk).toBe('unused');
    // status counts 없이도 같은 규칙
    expect(mapUserMappingRow(item({ channel_talk: null })).accounts.channel_talk).toBe('unused');
  });
});

describe('mapUserMappingRow — 상태 점(fullyMapped)', () => {
  it('atlassian·github·slack이 전부 실제 계정이면 녹색이다', () => {
    const row = mapUserMappingRow(item(), counts());
    expect(row.fullyMapped).toBe(true);
  });

  it('채널톡 미매핑은 감점하지 않는다 — 매니저가 아닌 이용자도 녹색일 수 있다', () => {
    const row = mapUserMappingRow(item({ channel_talk: null }), counts());
    expect(row.fullyMapped).toBe(true);
  });

  it('미사용 추론 셀은 실제 계정이 아니므로 감점한다', () => {
    const row = mapUserMappingRow(item({ github: null }), counts());
    expect(row.accounts.github).toBe('unused');
    expect(row.fullyMapped).toBe(false);
  });

  it('빈 name·identifier 계정은 미연동으로 계산돼 fullyMapped를 깬다', () => {
    const row = mapUserMappingRow(item({ github: { name: null, identifier: null, picture: null } }), counts());
    expect(row.fullyMapped).toBe(false);
  });
});
