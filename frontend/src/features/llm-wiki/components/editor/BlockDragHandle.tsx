'use client';

import { useCallback, useRef } from 'react';
import DragHandle from '@tiptap/extension-drag-handle-react';
import type { Node } from '@tiptap/pm/model';
import type { Editor } from '@tiptap/react';

import IconAdd from '@/public/icons/icon/add.svg';
import IconDragIndicator from '@/public/icons/icon/drag_indicator.svg';

export interface BlockDragHandleProps {
  editor: Editor | null;
}

/**
 * 블록 드래그 핸들과 블록 추가(+) 버튼. 시안이 없어 시각은 최소로 뒀다.
 * +는 아래에 빈 문단을 만들고 '/'를 삽입한다 — 메뉴를 직접 열지 않아 상태 배선이 중복되지 않는다.
 */
export default function BlockDragHandle({ editor }: BlockDragHandleProps) {
  // 클릭 시점에만 읽으므로 state가 아니라 ref다 — 호버 이동마다 리렌더하지 않는다.
  const hovered = useRef<{ node: Node | null; pos: number }>({ node: null, pos: -1 });

  const handleNodeChange = useCallback(({ node, pos }: { node: Node | null; editor: Editor; pos: number }) => {
    hovered.current = { node, pos };
  }, []);

  const insertBlockBelow = useCallback(() => {
    if (!editor) return;
    const { node, pos } = hovered.current;

    // 호버 추적이 없으면 현재 선택이 속한 최상위 블록 뒤로 폴백한다.
    const after =
      node && pos >= 0 ? pos + node.nodeSize : editor.state.selection.$to.after(1);

    editor
      .chain()
      .insertContentAt(after, { type: 'paragraph' })
      .focus(after + 1)
      .insertContent('/')
      .run();
  }, [editor]);

  if (!editor) return null;

  return (
    <DragHandle editor={editor} onNodeChange={handleNodeChange}>
      <div className="flex items-center">
        <button
          type="button"
          aria-label="아래에 블록 추가"
          onClick={insertBlockBelow}
          className="text-icon-normal-alternative hover:bg-fill-normal-interaction-hover cursor-pointer rounded p-0.5"
        >
          <IconAdd aria-hidden className="size-5" />
        </button>
        <div
          data-testid="block-drag-handle"
          className="text-icon-normal-alternative hover:bg-fill-normal-interaction-hover cursor-grab rounded p-0.5 active:cursor-grabbing"
        >
          <IconDragIndicator aria-hidden className="size-5" />
        </div>
      </div>
    </DragHandle>
  );
}
