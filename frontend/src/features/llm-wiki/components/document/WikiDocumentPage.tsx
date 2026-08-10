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
        페이지 헤더 — 공용 WikiPageHeader의 detail 변형(브레드크럼 체인).
        문서 시안의 52px 바가 이것이고, 아래 WikiDocumentMeta(카드 안 제목·작성정보)와는
        다른 층위다(Figma 17735:187317 vs 17735:187320).

        badge는 비워둔다 — 상태 태그 워크스트림이 게이트 대기 중이라 공급원이 없다.
        actions(⋯ 메뉴)도 비워둔다 — 시안에 아이콘은 있으나 메뉴 항목이 정의돼 있지 않다.
        헤더가 "메뉴 내용은 소비처가 정한다"고 남겨둔 자리인데, 우리에게 정할 근거가 없다.

        onBreadcrumbClick도 넘기지 않는다 — 채널·폴더 화면 라우트가 아직 없다.
        핸들러 없이도 이전 마디는 버튼으로 렌더되므로, 라우트가 생기면 한 줄만 더하면 된다.
      */}
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
