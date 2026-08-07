import { mergeAttributes, Node } from '@tiptap/core';

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    callout: {
      /** 현재 블록을 콜아웃으로 감싼다. 이미 콜아웃 안이면 푼다. */
      toggleCallout: () => ReturnType;
    };
  }
}

/**
 * 콜아웃 블록. Tiptap에 없어 직접 만든 유일한 노드다 (스펙 §2).
 *
 * 종류 구분(정보/경고 등)은 넣지 않는다 — 디자이너 시안이 없고(design-request 대기),
 * 시각은 배경 fill 토큰 하나로 최소만 잡는다. Notion처럼 아이콘·색 선택이 붙는 건
 * 시안 도착 후다. content가 'block+'라 콜아웃 안에 목록·코드도 들어간다(템플릿과 동일).
 */
export const Callout = Node.create({
  name: 'callout',
  group: 'block',
  content: 'block+',
  defining: true,

  parseHTML() {
    return [{ tag: 'div[data-type="callout"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'callout',
        class: 'bg-fill-normal-strong rounded-lg p-4',
      }),
      0,
    ];
  },

  addCommands() {
    return {
      toggleCallout:
        () =>
        ({ commands, editor }) => {
          if (editor.isActive('callout')) {
            return commands.lift('callout');
          }
          return commands.wrapIn('callout');
        },
    };
  },
});
