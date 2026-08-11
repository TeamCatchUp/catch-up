import { Extension } from '@tiptap/core';

/**
 * origin·claimIds attrs가 붙는 노드 목록.
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

/**
 * origin·claimIds attrs를 기존 노드에 얹어 왕복 보존만 한다 — 렌더하지 않는다.
 * 한계: setContent/getJSON 경로만 보존되고, DOM을 거치는 클립보드 복사·붙여넣기에서는 사라진다.
 */
export const WikiBlockAttrs = Extension.create({
  name: 'wikiBlockAttrs',

  addGlobalAttributes() {
    return [
      {
        types: [...WIKI_BLOCK_ATTR_TYPES],
        attributes: {
          origin: {
            default: null,
            // DOM으로 나가지 않는다. 렌더용이 아니라 왕복 보존용이다.
            renderHTML: () => ({}),
            parseHTML: () => null,
          },
          claimIds: {
            default: null,
            renderHTML: () => ({}),
            parseHTML: () => null,
          },
        },
      },
    ];
  },
});
