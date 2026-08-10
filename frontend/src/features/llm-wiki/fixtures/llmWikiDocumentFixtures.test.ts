import { describe, expect, it } from 'vitest';

import { findWikiDocument, WIKI_DOCUMENT_FIXTURES } from './llmWikiDocumentFixtures';

describe('llmWikiDocumentFixtures', () => {
  it('픽스처가 하나 이상 있다 — 없으면 아래 검사가 공허하게 통과한다', () => {
    expect(WIKI_DOCUMENT_FIXTURES.length).toBeGreaterThan(0);
  });

  it('발행본과 제안본의 내용이 다르다 — 같으면 모드 전환이 화면에서 검증되지 않는다', () => {
    for (const doc of WIKI_DOCUMENT_FIXTURES) {
      expect(JSON.stringify(doc.proposalDoc)).not.toBe(JSON.stringify(doc.publishedDoc));
    }
  });

  it('제안본이 발행본보다 블록이 많다 — AI가 내용을 더한 상태를 대표한다', () => {
    for (const doc of WIKI_DOCUMENT_FIXTURES) {
      const published = doc.publishedDoc.content?.length ?? 0;
      const proposed = doc.proposalDoc.content?.length ?? 0;
      expect(proposed).toBeGreaterThan(published);
    }
  });

  it('breadcrumbs의 마지막 마디가 문서 제목이다 — 헤더가 그 마디를 현재 페이지로 강조한다', () => {
    for (const doc of WIKI_DOCUMENT_FIXTURES) {
      expect(doc.breadcrumbs.length).toBeGreaterThan(0);
      expect(doc.breadcrumbs.at(-1)!.label).toBe(doc.title);
    }
  });

  it('id가 중복되지 않는다 — 조회가 엉킨다', () => {
    const ids = WIKI_DOCUMENT_FIXTURES.map((doc) => doc.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('findWikiDocument는 있는 id를 찾는다', () => {
    const first = WIKI_DOCUMENT_FIXTURES[0]!;
    expect(findWikiDocument(first.id)).toBe(first);
  });

  it('findWikiDocument는 없는 id에 undefined를 준다 — 라우트가 notFound()로 가는 근거', () => {
    expect(findWikiDocument('없는-문서-id')).toBeUndefined();
  });
});
