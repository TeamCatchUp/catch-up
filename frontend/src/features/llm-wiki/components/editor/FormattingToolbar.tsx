'use client';

import { useState } from 'react';
import type { Editor } from '@tiptap/core';
import { useEditorState } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

/** 블록 전환 대상 — 노션 turn-into와 같은 목록. 표·구분선은 "전환"이 성립하지 않아 뺀다. */
const TURN_INTO: readonly { label: string; isActive: (e: Editor) => boolean; run: (e: Editor) => void }[] = [
  { label: '본문', isActive: (e) => e.isActive('paragraph'), run: (e) => e.chain().focus().setParagraph().run() },
  {
    label: '제목 1',
    isActive: (e) => e.isActive('heading', { level: 1 }),
    run: (e) => e.chain().focus().setHeading({ level: 1 }).run(),
  },
  {
    label: '제목 2',
    isActive: (e) => e.isActive('heading', { level: 2 }),
    run: (e) => e.chain().focus().setHeading({ level: 2 }).run(),
  },
  {
    label: '제목 3',
    isActive: (e) => e.isActive('heading', { level: 3 }),
    run: (e) => e.chain().focus().setHeading({ level: 3 }).run(),
  },
  {
    label: '글머리 목록',
    isActive: (e) => e.isActive('bulletList'),
    run: (e) => e.chain().focus().toggleBulletList().run(),
  },
  {
    label: '번호 목록',
    isActive: (e) => e.isActive('orderedList'),
    run: (e) => e.chain().focus().toggleOrderedList().run(),
  },
  { label: '체크박스', isActive: (e) => e.isActive('taskList'), run: (e) => e.chain().focus().toggleTaskList().run() },
  {
    label: '인용',
    isActive: (e) => e.isActive('blockquote'),
    run: (e) => e.chain().focus().toggleBlockquote().run(),
  },
  { label: '코드', isActive: (e) => e.isActive('codeBlock'), run: (e) => e.chain().focus().toggleCodeBlock().run() },
  { label: '콜아웃', isActive: (e) => e.isActive('callout'), run: (e) => e.chain().focus().toggleCallout().run() },
];

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

  // 이 셀렉터는 "모든" 트랜잭션마다 돈다 — 타이핑 한 글자도 트랜잭션이다.
  // 전부 계산하면 isActive가 매 키 입력마다 20회 넘게 도는데(마크 7 + 정렬 3 + 블록 스캔 10),
  // 툴바는 선택이 있을 때만 보이므로 접힌 선택(=타이핑 중)에서는 계산 자체를 건너뛴다.
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      if (e.state.selection.empty) return null;
      return {
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
        blockLabel: TURN_INTO.find((entry) => entry.isActive(e))?.label ?? '본문',
      };
    },
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
      {/* state가 null이면 선택이 접혀 있다 — 툴바 DOM 자체를 만들지 않는다.
          BubbleMenu는 계속 마운트해 둔다(플러그인 add/remove가 더 비싸다). */}
      {state === null ? null : (
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" aria-label="블록 전환" className={`${BUTTON_CLASS} gap-1`}>
                  {state.blockLabel}
                  <svg aria-hidden viewBox="0 0 20 20" className="size-3" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                {TURN_INTO.map((entry) => (
                  <DropdownMenuItem key={entry.label} onSelect={() => entry.run(editor)}>
                    {entry.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <span aria-hidden className="bg-line-normal-neutral mx-0.5 h-5 w-px" />
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
      )}
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
