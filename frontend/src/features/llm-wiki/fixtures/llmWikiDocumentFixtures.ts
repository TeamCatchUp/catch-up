import type { JSONContent } from '@tiptap/react';

import type { DocumentBreadcrumb } from '../types/llmWikiModel';

/**
 * 문서 화면 픽스처(Tiptap JSON). 문서 조회 API가 없어 라우트가 이걸로 렌더한다.
 * 열람은 발행본, 편집은 제안본이라 둘의 내용이 달라야 모드 전환이 검증된다.
 */
export interface WikiDocumentFixture {
  id: string;
  title: string;
  /** [SPEC] 작성자. 백엔드에 대응 필드가 없다 */
  authorName: string;
  /** [SPEC] 표시용 상대시각 문자열. 계산은 범위 밖 */
  createdLabel: string;
  /** 채널 > 폴더 > 현재페이지. 마지막 마디는 title과 같아야 한다 — 테스트가 지킨다. */
  breadcrumbs: readonly DocumentBreadcrumb[];
  /** 이 문서에 달린 제안. 편집 진입의 1급 키다 */
  proposalId: string;
  /** 발행본 — 열람 모드에서 보여준다 */
  publishedDoc: JSONContent;
  /** 제안본 — 편집 모드에서 열린다 */
  proposalDoc: JSONContent;
}

const heading = (text: string): JSONContent => ({
  type: 'heading',
  attrs: { level: 2 },
  content: [{ type: 'text', text }],
});

const paragraph = (text: string, attrs: Record<string, unknown> = {}): JSONContent => ({
  type: 'paragraph',
  attrs,
  content: [{ type: 'text', text }],
});

export const WIKI_DOCUMENT_FIXTURES: readonly WikiDocumentFixture[] = [
  {
    id: 'doc-billing-failure',
    title: '결제 실패 대응 가이드',
    authorName: '팀원F',
    createdLabel: '23시간 전',
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '장애 대응' },
      { kind: 'document', label: '결제 실패 대응 가이드' },
    ],
    proposalId: 'prop-billing-1',
    publishedDoc: {
      type: 'doc',
      content: [
        heading('현황'),
        paragraph('8월 들어 결제 실패가 증가했다.', { origin: 'system', claimIds: ['c_1'] }),
        paragraph('검토자 메모: 원인 확인 중.', { origin: 'human' }),
      ],
    },
    proposalDoc: {
      type: 'doc',
      content: [
        heading('현황'),
        paragraph('8월 들어 결제 실패가 3.2%까지 올랐다.', { origin: 'system', claimIds: ['c_1', 'c_2'] }),
        heading('원인'),
        paragraph('PG사 응답 지연이 주된 원인으로 확인됐다.', { origin: 'system', claimIds: ['c_3'] }),
        paragraph('검토자 메모: 원인 확인 중.', { origin: 'human' }),
      ],
    },
  },
];

/** 없는 id면 undefined — 라우트는 이걸 받아 notFound()를 호출한다 */
export function findWikiDocument(id: string): WikiDocumentFixture | undefined {
  return WIKI_DOCUMENT_FIXTURES.find((doc) => doc.id === id);
}
