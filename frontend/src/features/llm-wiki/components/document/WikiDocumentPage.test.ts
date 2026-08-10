import { describe, expect, it } from 'vitest';

import { WIKI_DOCUMENT_FIXTURES } from '../../fixtures/llmWikiDocumentFixtures';
import { resolveDocumentView } from './WikiDocumentPage';

const doc = WIKI_DOCUMENT_FIXTURES[0]!;

describe('resolveDocumentView', () => {
  it('proposalId가 없으면 열람 전용이고 발행본을 준다', () => {
    const result = resolveDocumentView(doc, null);
    expect(result.mode).toBe('view');
    expect(result.canEdit).toBe(false);
    expect(result.doc).toBe(doc.publishedDoc);
  });

  it('proposalId가 맞으면 편집 모드이고 제안본을 준다', () => {
    const result = resolveDocumentView(doc, doc.proposalId);
    expect(result.mode).toBe('edit');
    expect(result.canEdit).toBe(true);
    expect(result.doc).toBe(doc.proposalDoc);
  });

  it('proposalId가 이 문서 것이 아니면 열람 전용으로 강등한다 — 404가 아니다', () => {
    const result = resolveDocumentView(doc, 'prop-다른문서-99');
    expect(result.mode).toBe('view');
    expect(result.canEdit).toBe(false);
    expect(result.doc).toBe(doc.publishedDoc);
  });

  it('빈 문자열 proposalId도 없는 것으로 본다 — ?proposalId= 만 붙은 URL', () => {
    const result = resolveDocumentView(doc, '');
    expect(result.mode).toBe('view');
    expect(result.canEdit).toBe(false);
  });
});
