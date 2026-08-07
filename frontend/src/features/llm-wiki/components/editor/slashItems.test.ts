import { describe, expect, it } from 'vitest';

import { filterSlashItems, SLASH_ITEMS } from './slashItems';

describe('filterSlashItems', () => {
  it('빈 쿼리는 전체를 준다', () => {
    expect(filterSlashItems(SLASH_ITEMS, '')).toHaveLength(SLASH_ITEMS.length);
  });

  it('한글 라벨 부분 일치로 찾는다', () => {
    const result = filterSlashItems(SLASH_ITEMS, '제목');
    expect(result.length).toBeGreaterThan(0);
    for (const item of result) {
      expect(item.id.startsWith('heading')).toBe(true);
    }
  });

  it('영문 keyword로도 같은 항목을 찾는다 — 한글만 되면 안 된다', () => {
    const korean = filterSlashItems(SLASH_ITEMS, '제목').map((item) => item.id);
    const english = filterSlashItems(SLASH_ITEMS, 'heading').map((item) => item.id);
    expect(english).toEqual(korean);
  });

  it('대소문자를 가리지 않는다', () => {
    const upper = filterSlashItems(SLASH_ITEMS, 'CODE');
    // 양쪽 다 []면 공허하게 통과하므로 비어 있지 않음을 먼저 못박는다
    expect(upper.length).toBeGreaterThan(0);
    expect(upper).toEqual(filterSlashItems(SLASH_ITEMS, 'code'));
  });

  it('앞뒤 공백을 무시한다', () => {
    const padded = filterSlashItems(SLASH_ITEMS, '  목록  ');
    expect(padded.length).toBeGreaterThan(0);
    expect(padded).toEqual(filterSlashItems(SLASH_ITEMS, '목록'));
  });

  it('화면 문구로 검색된다 — description의 "순서"가 keywords에도 있어야 한다', () => {
    const ids = filterSlashItems(SLASH_ITEMS, '순서').map((item) => item.id);
    expect(ids).toContain('bullet-list');
    expect(ids).toContain('ordered-list');
  });

  it('맞는 게 없으면 빈 배열이다 — 전체로 되돌아가지 않는다', () => {
    expect(filterSlashItems(SLASH_ITEMS, 'zzzz없는항목zzzz')).toEqual([]);
  });
});

describe('SLASH_ITEMS', () => {
  it('id가 중복되지 않는다 — cmdk value가 겹치면 하이라이트가 엉킨다', () => {
    const ids = SLASH_ITEMS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('모든 항목이 한글 keyword를 하나 이상 갖는다', () => {
    for (const item of SLASH_ITEMS) {
      const hasKorean = item.keywords.some((keyword) => /[가-힣]/.test(keyword));
      expect(hasKorean, `${item.id}에 한글 keyword가 없다`).toBe(true);
    }
  });

  it('모든 항목이 영문 keyword를 하나 이상 갖는다', () => {
    for (const item of SLASH_ITEMS) {
      const hasLatin = item.keywords.some((keyword) => /[a-z]/i.test(keyword));
      expect(hasLatin, `${item.id}에 영문 keyword가 없다`).toBe(true);
    }
  });
});
