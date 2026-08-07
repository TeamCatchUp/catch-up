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
] as const satisfies readonly string[];

/**
 * origin(블록을 누가 만들었나)·claimIds(어느 근거에서 나왔나)를 기존 노드에 얹는다.
 *
 * 화면에 렌더하지 않는다. 우측 근거 패널이 MVP에서 빠지면서 이 값을 보여줄 자리가 없어졌다.
 * 그런데도 자리를 파두는 이유: ProseMirror는 스키마에 없는 attrs를 조용히 버린다.
 * 나중에 백엔드가 claim_ids를 실어 보낼 때 자리가 없으면 로드 → 편집 → 저장 한 번에 사라지고,
 * 화면에 안 보이는 값이라 눈으로는 절대 알 수 없다.
 *
 * 알려진 한계: 왕복 보존은 setContent/getJSON 경로만이다. renderHTML이 no-op이라 DOM을 거치는
 * 클립보드 복사→붙여넣기에서는 이 값들이 사라진다(에디터 내부 드래그 이동은 slice를 그대로 써서 안전).
 * 해법은 clipboard 플러그인 — blocks[] 어댑터 작업에서 다룬다.
 *
 * 근거: docs/specs/2026-08-07-llm-wiki-tiptap-editor-design.md §5
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
