import { describe, expect, it } from 'vitest';

import type { UserMappingRow } from '../types/userMappingModel';
import { findUnappliedAtlassianUnused } from './findUnappliedAtlassianUnused';

const row = (id: string, atlassian: UserMappingRow['accounts']['atlassian']): UserMappingRow => ({
  id,
  user: { name: `사용자 ${id}` },
  fullyMapped: false,
  accounts: { atlassian, github: null, slack: null, channel_talk: null },
});

describe('findUnappliedAtlassianUnused', () => {
  it('미사용 저장 후에도 계정이 남아 있는 행만 골라낸다', () => {
    const rows = [
      row('1', { name: 'Confluence 계정', identifier: 'a@b.c', picture: null }),
      row('2', null),
    ];
    const unapplied = findUnappliedAtlassianUnused(rows, ['1', '2']);
    expect(unapplied.map((r) => r.id)).toEqual(['1']);
  });

  it('저장 대상이 아닌 행은 계정이 있어도 무시한다', () => {
    const rows = [row('1', { name: '계정', identifier: 'a@b.c', picture: null })];
    expect(findUnappliedAtlassianUnused(rows, ['2'])).toEqual([]);
  });

  it('셀 값이 unused면 반영된 것으로 본다', () => {
    const rows = [row('1', 'unused')];
    expect(findUnappliedAtlassianUnused(rows, ['1'])).toEqual([]);
  });

  it('재조회 페이지에 없는 행은 판정하지 않는다', () => {
    expect(findUnappliedAtlassianUnused([], ['1'])).toEqual([]);
  });
});
