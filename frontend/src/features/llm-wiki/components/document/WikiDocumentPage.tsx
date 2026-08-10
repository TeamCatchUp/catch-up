'use client';

import type { JSONContent } from '@tiptap/react';

import type { WikiDocumentFixture } from '../../fixtures/llmWikiDocumentFixtures';

export interface DocumentView {
  mode: 'view' | 'edit';
  doc: JSONContent;
  canEdit: boolean;
}

/**
 * 편집 여부는 로컬 상태가 아니라 URL의 proposalId에서 파생된다.
 *
 * 근거(스펙 §2·§5): 편집 대상은 제안본이고, 제안본 blocks[]는 GET /queue/{proposal_id}
 * 에만 있다. 즉 proposalId는 진입 경로 표시가 아니라 편집 대상 식별자다 — 그것이 없으면
 * 고칠 물건 자체가 없다.
 *
 * 불일치·누락은 404가 아니라 열람 전용 강등이다. 발행본 열람은 정상 기능이기 때문이다.
 * 조용히 실패하지 않게, 호출부는 canEdit=false일 때 편집 진입점을 아예 렌더하지 않는다
 * (비활성 버튼으로 두면 "권한이 없나?"가 되는데 실제로는 대상이 없는 것이다).
 */
export function resolveDocumentView(document: WikiDocumentFixture, proposalId: string | null): DocumentView {
  const matches = proposalId != null && proposalId.length > 0 && proposalId === document.proposalId;

  return matches
    ? { mode: 'edit', doc: document.proposalDoc, canEdit: true }
    : { mode: 'view', doc: document.publishedDoc, canEdit: false };
}
