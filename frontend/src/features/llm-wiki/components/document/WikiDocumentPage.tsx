'use client';

import type { JSONContent } from '@tiptap/react';

import type { WikiDocumentFixture } from '../../fixtures/llmWikiDocumentFixtures';
import WikiEditor from '../editor/WikiEditor';
import DevEditToggle from './DevEditToggle';
import WikiDocumentMeta from './WikiDocumentMeta';

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

export interface WikiDocumentPageProps {
  document: WikiDocumentFixture;
  proposalId: string | null;
}

export default function WikiDocumentPage({ document, proposalId }: WikiDocumentPageProps) {
  const view = resolveDocumentView(document, proposalId);

  return (
    <section className="flex min-h-full flex-col">
      {/*
        페이지 헤더(브레드크럼 52px) 슬롯. 헤더 세션이 components/header/** 에 공용 셸을
        랜딩하면 여기 끼운다 — 조합 시점은 오케스트레이터가 공지한다. 그때까지 높이만 잡아
        아래 레이아웃이 헤더 유무로 흔들리지 않게 한다.
      */}
      <div aria-hidden className="border-line-normal-normal h-13 shrink-0 border-b" />

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

        {/* 편집 중에는 무엇을 보고 있는지 알려준다 — 모드에 따라 문서 내용 자체가 바뀐다(스펙 §5) */}
        {view.mode === 'edit' && (
          <p className="text-label-small text-text-normal-alternative">
            제안본을 편집 중입니다. 저장 기능은 아직 없어 새로고침하면 사라집니다.
          </p>
        )}

        {/*
          key={view.mode}가 필수다. WikiEditor는 uncontrolled라 initialContent가 최초 1회만
          반영되는데(에디터 스펙 §8), 모드가 바뀌면 문서 자체가 발행본↔제안본으로 갈린다.
          재마운트하지 않으면 내용이 안 바뀐다.
        */}
        <WikiEditor key={view.mode} initialContent={view.doc} editable={view.mode === 'edit'} />
      </div>
    </section>
  );
}
