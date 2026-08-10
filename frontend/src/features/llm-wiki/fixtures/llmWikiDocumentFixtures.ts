import type { JSONContent } from '@tiptap/react';

/**
 * 문서 화면 픽스처. 문서 조회 API가 없어 라우트가 이걸로 렌더한다.
 *
 * 발행본과 제안본을 둘 다 들고 있는 이유: 편집 대상은 제안본이고(스펙 §2),
 * 열람은 발행본이다. 둘의 내용이 달라야 모드 전환이 화면에서 실제로 검증된다 —
 * 같으면 편집을 눌러도 아무것도 안 바뀌어서 "제안본을 연다"는 계약이 공허해진다.
 *
 * llmWikiFixtures.ts(배치 소유 도메인 mock)와 합치지 않는다. 그쪽은 백엔드 ERD를
 * 따르는 계약이고 이건 화면 렌더용 Tiptap JSON이다.
 */
export interface WikiDocumentFixture {
  id: string;
  title: string;
  /** [SPEC] 작성자. 백엔드 큐 행에는 작성자 필드가 없다 — API 협상 대상 */
  authorName: string;
  /** [SPEC] "23시간 전" 같은 표시 문자열. 상대시각 계산은 이 범위 밖 */
  createdLabel: string;
  /** 이 문서에 달린 제안. 편집 진입의 1급 키다 */
  proposalId: string;
  /** 발행본 — 열람 모드에서 보여준다 */
  publishedDoc: JSONContent;
  /** 제안본 — 편집 모드에서 열린다. 발행본에 AI가 더한 내용이 반영된 상태 */
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
