import { describe, expect, it } from 'vitest';

import { resolveDocumentBlockText } from '../api/wikiDocumentMappers';
import {
  WIKI_DOCUMENT_BREADCRUMBS,
  WIKI_DOCUMENT_FIXTURE,
  WIKI_DOCUMENT_LAYOUT_FIXTURE,
} from './llmWikiDocumentFixtures';

describe('llmWikiDocumentFixtures', () => {
  it('블록이 하나 이상 있다 — 없으면 아래 검사가 공허하게 통과한다', () => {
    expect(WIKI_DOCUMENT_FIXTURE.blocks.length).toBeGreaterThan(0);
  });

  it('blockIndex가 자리 순서와 같고 중복되지 않는다 — 블록 고유 id가 없어 자리가 식별자다', () => {
    WIKI_DOCUMENT_FIXTURE.blocks.forEach((block, index) => {
      expect(block.blockIndex).toBe(index);
    });
  });

  it('산문 있는 블록과 없는 블록이 함께 있다 — 스토리에서 폴백이 검증되려면 둘 다 필요하다', () => {
    const blocks = WIKI_DOCUMENT_FIXTURE.blocks;
    expect(blocks.some((block) => block.narrative !== null)).toBe(true);
    expect(blocks.some((block) => block.narrative === null)).toBe(true);
  });

  it('산문 없는 블록의 body가 비어 있지 않다 — 비면 폴백해도 화면이 빈다', () => {
    for (const block of WIKI_DOCUMENT_FIXTURE.blocks) {
      expect(resolveDocumentBlockText(block).length).toBeGreaterThan(0);
    }
  });

  it('breadcrumbs의 마지막 마디가 문서 제목이다 — 헤더가 그 마디를 현재 페이지로 강조한다', () => {
    expect(WIKI_DOCUMENT_BREADCRUMBS.length).toBeGreaterThan(0);
    expect(WIKI_DOCUMENT_BREADCRUMBS.at(-1)!.label).toBe(WIKI_DOCUMENT_FIXTURE.title);
  });

  it('발행 시각은 ISO와 표시 문자열을 함께 갖는다 — 표시 문자열은 정렬에 쓸 수 없다', () => {
    expect(Number.isNaN(Date.parse(WIKI_DOCUMENT_FIXTURE.publishedAt))).toBe(false);
    expect(WIKI_DOCUMENT_FIXTURE.publishedLabel.length).toBeGreaterThan(0);
  });

  it('기본 표본은 layout이 비어 있다 — 양식 없는 종류와 구서버 응답의 자리다', () => {
    expect(WIKI_DOCUMENT_FIXTURE.layout).toEqual([]);
  });
});

describe('WIKI_DOCUMENT_LAYOUT_FIXTURE', () => {
  it('block과 placeholder 항목이 모두 있다 — 하나라도 빠지면 스토리가 그 경로를 덮지 못한다', () => {
    const kinds = new Set(WIKI_DOCUMENT_LAYOUT_FIXTURE.layout.map((item) => item.kind));
    expect(kinds).toEqual(new Set(['block', 'placeholder']));
  });

  it('block 항목이 가리키는 자리가 blocks에 실재한다', () => {
    for (const item of WIKI_DOCUMENT_LAYOUT_FIXTURE.layout) {
      if (item.kind === 'block') expect(WIKI_DOCUMENT_LAYOUT_FIXTURE.blocks[item.blockIndex]).toBeDefined();
    }
  });

  it('사용 상황과 지원 상태가 각 block으로 있다', () => {
    const headings = WIKI_DOCUMENT_LAYOUT_FIXTURE.layout.flatMap((item) => (item.kind === 'block' ? [item.heading] : []));
    expect(headings).toEqual(expect.arrayContaining(['사용 상황', '지원 상태']));
  });

  it('표시 순서가 저장 순서와 다르다 — 같으면 layout을 따르는지 드러나지 않는다', () => {
    const shown = WIKI_DOCUMENT_LAYOUT_FIXTURE.layout
      .filter((item) => item.kind === 'block')
      .map((item) => item.blockIndex);
    expect(shown).not.toEqual([...shown].sort((left, right) => left - right));
  });
});
