'use client';

import { useState } from 'react';
import type { Editor } from '@tiptap/core';
import { useEditorState } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';

/**
 * 선택 시 뜨는 플로팅 서식 툴바 (스펙 §12 — Notion-like 템플릿의 floating toolbar 대응).
 *
 * 버튼 글리프는 노션과 같은 문자 기반(B·I·U·S)이다 — 서식 아이콘 자산이 리포에 없고
 * (design-request 대기), 문자 글리프는 노션 자체가 쓰는 방식이라 임시 시각으로도 대표성이 있다.
 * 하이라이트는 <mark> 기본 시각을 버튼 글리프에 그대로 쓴다.
 */
export interface FormattingToolbarProps {
  editor: Editor;
}

const BUTTON_CLASS =
  'text-body-small text-text-normal-normal hover:bg-fill-normal-interaction-hover flex h-8 min-w-8 cursor-pointer items-center justify-center rounded px-1.5';
const ACTIVE_CLASS = 'bg-fill-normal-interaction-hover text-text-primary-normal';

function cls(active: boolean) {
  return `${BUTTON_CLASS} ${active ? ACTIVE_CLASS : ''}`;
}

export default function FormattingToolbar({ editor }: FormattingToolbarProps) {
  // 링크 입력 모드 — 툴바 내용이 입력창으로 바뀐다 (노션과 동일한 인라인 전환)
  const [linkDraft, setLinkDraft] = useState<string | null>(null);

  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      bold: e.isActive('bold'),
      italic: e.isActive('italic'),
      underline: e.isActive('underline'),
      strike: e.isActive('strike'),
      code: e.isActive('code'),
      highlight: e.isActive('highlight'),
      link: e.isActive('link'),
      alignLeft: e.isActive({ textAlign: 'left' }),
      alignCenter: e.isActive({ textAlign: 'center' }),
      alignRight: e.isActive({ textAlign: 'right' }),
    }),
  });

  const applyLink = () => {
    const href = linkDraft?.trim();
    if (href) {
      editor.chain().focus().extendMarkRange('link').setLink({ href }).run();
    } else {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
    }
    setLinkDraft(null);
  };

  return (
    <BubbleMenu editor={editor} updateDelay={100} options={{ placement: 'top', offset: 6 }}>
      <div
        role="toolbar"
        aria-label="텍스트 서식"
        // mousedown을 막지 않으면 버튼 클릭이 에디터 선택을 무너뜨려 서식이 빈 선택에 적용된다
        // (공용 command.tsx 삭제 버튼과 같은 처리). 링크 입력 모드에서는 input이 포커스를 가져야 하므로 예외.
        onMouseDown={(event) => {
          if (linkDraft === null) event.preventDefault();
        }}
        className="border-line-normal-normal bg-fill-normal-normal shadow-dropdown-menu flex items-center gap-0.5 rounded-lg border p-1"
      >
        {linkDraft !== null ? (
          <>
            <input
               
              autoFocus
              value={linkDraft}
              onChange={(event) => setLinkDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') applyLink();
                if (event.key === 'Escape') setLinkDraft(null);
              }}
              placeholder="https://…"
              className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive w-52 bg-transparent px-2 outline-none"
            />
            <button type="button" className={BUTTON_CLASS} onClick={applyLink}>
              적용
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              aria-label="굵게"
              aria-pressed={state.bold}
              className={cls(state.bold)}
              onClick={() => editor.chain().focus().toggleBold().run()}
            >
              <span className="font-bold">B</span>
            </button>
            <button
              type="button"
              aria-label="기울임"
              aria-pressed={state.italic}
              className={cls(state.italic)}
              onClick={() => editor.chain().focus().toggleItalic().run()}
            >
              <span className="italic">I</span>
            </button>
            <button
              type="button"
              aria-label="밑줄"
              aria-pressed={state.underline}
              className={cls(state.underline)}
              onClick={() => editor.chain().focus().toggleUnderline().run()}
            >
              <span className="underline">U</span>
            </button>
            <button
              type="button"
              aria-label="취소선"
              aria-pressed={state.strike}
              className={cls(state.strike)}
              onClick={() => editor.chain().focus().toggleStrike().run()}
            >
              <span className="line-through">S</span>
            </button>
            <button
              type="button"
              aria-label="인라인 코드"
              aria-pressed={state.code}
              className={cls(state.code)}
              onClick={() => editor.chain().focus().toggleCode().run()}
            >
              <span className="font-mono text-xs">{'</>'}</span>
            </button>
            <button
              type="button"
              aria-label="하이라이트"
              aria-pressed={state.highlight}
              className={cls(state.highlight)}
              onClick={() => editor.chain().focus().toggleHighlight().run()}
            >
              <mark className="rounded-sm px-0.5">가</mark>
            </button>
            <span aria-hidden className="bg-line-normal-neutral mx-0.5 h-5 w-px" />
            <button
              type="button"
              aria-label="링크"
              aria-pressed={state.link}
              className={cls(state.link)}
              onClick={() => {
                if (state.link) {
                  editor.chain().focus().extendMarkRange('link').unsetLink().run();
                } else {
                  setLinkDraft(editor.getAttributes('link').href ?? '');
                }
              }}
            >
              링크
            </button>
            <span aria-hidden className="bg-line-normal-neutral mx-0.5 h-5 w-px" />
            <button
              type="button"
              aria-label="왼쪽 정렬"
              aria-pressed={state.alignLeft}
              className={cls(state.alignLeft)}
              onClick={() => editor.chain().focus().toggleTextAlign('left').run()}
            >
              <AlignGlyph variant="left" />
            </button>
            <button
              type="button"
              aria-label="가운데 정렬"
              aria-pressed={state.alignCenter}
              className={cls(state.alignCenter)}
              onClick={() => editor.chain().focus().toggleTextAlign('center').run()}
            >
              <AlignGlyph variant="center" />
            </button>
            <button
              type="button"
              aria-label="오른쪽 정렬"
              aria-pressed={state.alignRight}
              className={cls(state.alignRight)}
              onClick={() => editor.chain().focus().toggleTextAlign('right').run()}
            >
              <AlignGlyph variant="right" />
            </button>
          </>
        )}
      </div>
    </BubbleMenu>
  );
}

/** 정렬 글리프 — 자산 없는 아이콘의 임시 인라인 SVG (스펙 §12 아이콘 방침) */
function AlignGlyph({ variant }: { variant: 'left' | 'center' | 'right' }) {
  const x2 = { left: [16, 10, 16], center: [16, 13, 16], right: [16, 16, 16] }[variant];
  const x1 = { left: [4, 4, 4], center: [4, 7, 4], right: [4, 10, 4] }[variant];
  return (
    <svg aria-hidden viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1={x1[0]} y1="5" x2={x2[0]} y2="5" />
      <line x1={x1[1]} y1="10" x2={x2[1]} y2="10" />
      <line x1={x1[2]} y1="15" x2={x2[2]} y2="15" />
    </svg>
  );
}
