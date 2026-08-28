import { Extension } from '@tiptap/core';

/**
 * 서버 블록 필드가 붙는 노드 목록.
 * 새 블록을 추가하면 여기에 이름을 더한다 — 노드 파일을 열 필요는 없다.
 */
export const WIKI_BLOCK_ATTR_TYPES = [
  'paragraph',
  'heading',
  'blockquote',
  'codeBlock',
  'bulletList',
  'orderedList',
  'listItem',
  'horizontalRule',
  // 표의 행·셀은 블록이 아니라 표 내부 구조라 제외한다
  'taskList',
  'taskItem',
  'table',
  'callout',
] as const satisfies readonly string[];

/** 왕복 보존만 하고 렌더하지 않는 attr의 공통 정의 — 스키마에 자리만 판다. */
const preserved = { default: null, renderHTML: () => ({}), parseHTML: () => null };

/**
 * 서버가 블록에 붙이는 필드를 기존 노드에 얹어 왕복 보존만 한다 — 렌더하지 않는다.
 * 스키마에 없는 attr은 ProseMirror가 조용히 버리므로, 화면에 안 쓰는 값도 자리를 파둬야 한다.
 *
 * blockContentHash는 판정 요청의 필수값이다 — 잃으면 그 블록을 승인·반려할 수 없다.
 * variants는 null(후보 없는 블록)과 빈 배열(다투는데 후보가 빔)이 다른 뜻이라 뭉개지 않는다.
 * 한계: setContent/getJSON 경로만 보존되고, DOM을 거치는 클립보드 복사·붙여넣기에서는 사라진다.
 */
export const WikiBlockAttrs = Extension.create({
  name: 'wikiBlockAttrs',

  addGlobalAttributes() {
    return [
      {
        types: [...WIKI_BLOCK_ATTR_TYPES],
        attributes: {
          origin: preserved,
          claimIds: preserved,
          proposalIds: preserved,
          ontologyVersion: preserved,
          blockIndex: preserved,
          blockContentHash: preserved,
          variants: preserved,
        },
      },
    ];
  },
});
