'use client';

import type { JSONContent } from '@tiptap/react';

import type { WikiDocumentFixture } from '../../fixtures/llmWikiDocumentFixtures';
import WikiEditor from '../editor/WikiEditor';
import WikiPageHeader from '../header/WikiPageHeader';
import DevEditToggle from './DevEditToggle';
import WikiDocumentMeta from './WikiDocumentMeta';

export interface DocumentView {
  mode: 'view' | 'edit';
  doc: JSONContent;
  canEdit: boolean;
}

/**
 * 편집 여부는 로컬 상태가 아니라 URL의 proposalId에서 파생된다 — 편집 대상은 제안본이기 때문이다.
 * proposalId 불일치·누락은 404가 아니라 열람 전용 강등이다.
 */
export function resolveDocumentView(document: WikiDocumentFixture, proposalId: string | null): DocumentView {
  const matches = proposalId != null && proposalId.length > 0 && proposalId === document.proposalId;

  return matches
    ? { mode: 'edit', doc: document.proposalDoc, canEdit: true }
    : { mode: 'view', doc: document.publishedDoc, canEdit: false };
}

export interface WikiDocumentPageProps {
  document: WikiDocumentFixture;
  proposalId: string | null;
}

export default function WikiDocumentPage({ document, proposalId }: WikiDocumentPageProps) {
  const view = resolveDocumentView(document, proposalId);

  return (
    <section className="flex min-h-full flex-col">
      {/* 페이지 헤더. badge·actions·onBreadcrumbClick은 공급원·라우트가 없어 비워둔다. */}
      <WikiPageHeader variant="detail" breadcrumbs={document.breadcrumbs} />

      <div className="mx-auto flex w-full max-w-260 flex-1 flex-col gap-6 px-6 py-9">
        <WikiDocumentMeta
          title={document.title}
          authorName={document.authorName}
          createdLabel={document.createdLabel}
        >
          <DevEditToggle
            documentId={document.id}
            proposalId={document.proposalId}
            isEditing={view.mode === 'edit'}
          />
        </WikiDocumentMeta>

        {/* 편집 중에는 무엇을 보고 있는지 알려준다 — 모드에 따라 문서 내용 자체가 바뀐다 */}
        {view.mode === 'edit' && (
          <p className="text-label-small text-text-normal-alternative">
            제안본을 편집 중입니다. 저장 기능은 아직 없어 새로고침하면 사라집니다.
          </p>
        )}

        {/* key={view.mode} 필수 — WikiEditor는 uncontrolled라 재마운트하지 않으면 문서가 안 바뀐다. */}
        <WikiEditor key={view.mode} initialContent={view.doc} editable={view.mode === 'edit'} />
      </div>
    </section>
  );
}
