'use client';

import { useCallback, useRef } from 'react';
import DragHandle from '@tiptap/extension-drag-handle-react';
import type { Node } from '@tiptap/pm/model';
import type { Editor } from '@tiptap/react';

import IconDragIndicator from '@/public/icons/icon/drag_indicator.svg';

import { IconPlus } from './editorIcons';

export interface BlockDragHandleProps {
  editor: Editor | null;
}

/**
 * 블록 드래그 핸들 + 블록 추가(+) 버튼 — Notion-like 템플릿의 좌측 컨트롤 대응(스펙 §12).
 *
 * 명세에도 Figma에도 이 컨트롤이 없다 — 위치·크기·호버 타이밍은 전부 우리가 정한 값이다.
 * 시각은 최소로 뒀고 시안 요청이 design-request에 올라가 있다.
 *
 * +는 노션과 같이 "현재 블록 아래에 빈 문단을 만들고 슬래시 메뉴를 연다".
 * 슬래시 메뉴를 직접 열지 않고 '/'를 삽입한다 — Suggestion 트리거와 같은 경로라
 * 메뉴 상태 배선을 중복으로 만들지 않는다.
 */
export default function BlockDragHandle({ editor }: BlockDragHandleProps) {
  // 클릭 시점에만 읽으므로 state가 아니라 ref다 — 호버 이동마다 리렌더할 이유가 없다.
  const hovered = useRef<{ node: Node | null; pos: number }>({ node: null, pos: -1 });

  const handleNodeChange = useCallback(({ node, pos }: { node: Node | null; editor: Editor; pos: number }) => {
    hovered.current = { node, pos };
  }, []);

  const insertBlockBelow = useCallback(() => {
    if (!editor) return;
    const { node, pos } = hovered.current;

    // 호버 추적이 없으면(플러그인이 mousemove를 아직 못 받은 경우) 현재 선택이 속한
    // 최상위 블록 뒤로 폴백한다 — 버튼이 보이는데 클릭이 무시되는 것보다 낫다.
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
          <IconPlus className="size-5" />
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
