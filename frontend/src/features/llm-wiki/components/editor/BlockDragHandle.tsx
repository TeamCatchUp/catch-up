'use client';

import type { Editor } from '@tiptap/core';
import DragHandle from '@tiptap/extension-drag-handle-react';

import IconDragIndicator from '@/public/icons/icon/drag_indicator.svg';

export interface BlockDragHandleProps {
  editor: Editor | null;
}

/**
 * 블록 드래그 핸들.
 *
 * 명세에도 Figma에도 드래그 재정렬이 없다 — 위치·크기·호버 타이밍은 전부 우리가 정한 값이다.
 * 그래서 시각을 최소로 뒀고, 시안 요청이 design-request에 올라가 있다.
 * 스토리의 designSource: 'dev-preview'가 "시안 없음"을 기계가 읽을 수 있게 기록한다.
 */
export default function BlockDragHandle({ editor }: BlockDragHandleProps) {
  if (!editor) return null;

  return (
    <DragHandle editor={editor}>
      <div
        data-testid="block-drag-handle"
        className="text-icon-normal-alternative hover:bg-fill-normal-interaction-hover cursor-grab rounded p-0.5 active:cursor-grabbing"
      >
        <IconDragIndicator aria-hidden className="size-5" />
      </div>
    </DragHandle>
  );
}
