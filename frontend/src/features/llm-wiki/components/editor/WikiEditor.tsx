'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Highlight from '@tiptap/extension-highlight';
import { TableKit } from '@tiptap/extension-table';
import TaskItem from '@tiptap/extension-task-item';
import TaskList from '@tiptap/extension-task-list';
import TextAlign from '@tiptap/extension-text-align';
import UniqueID from '@tiptap/extension-unique-id';
import { EditorContent, type JSONContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

import { Popover, PopoverAnchor, PopoverContent } from '@/shared/components/ui/popover';

import type { EmojiMenuState, SlashMenuHandle, SlashMenuState } from '../../types/llmWikiEditor';
import BlockDragHandle from './BlockDragHandle';
import EmojiMenu from './EmojiMenu';
import { Callout } from './extensions/callout';
import { EmojiCommand } from './extensions/emojiCommand';
import { SlashCommand } from './extensions/slashCommand';
import { WIKI_BLOCK_ATTR_TYPES, WikiBlockAttrs } from './extensions/wikiBlockAttrs';
import FormattingToolbar from './FormattingToolbar';
import SlashMenu from './SlashMenu';

/**
 * WikiEditor가 쓰는 확장 목록. 테스트가 같은 목록으로 왕복을 검증한다.
 * UniqueID 대상 노드는 attrs 보존 목록과 같은 집합이어야 한다 — 갈라지면 attrs만 남고 id가 없는 블록이 생긴다.
 */
export const WIKI_EDITOR_EXTENSIONS = [
  StarterKit,
  WikiBlockAttrs,
  UniqueID.configure({ types: [...WIKI_BLOCK_ATTR_TYPES] }),
  Highlight,
  TextAlign.configure({ types: ['heading', 'paragraph'] }),
  TaskList,
  TaskItem.configure({ nested: true }),
  TableKit.configure({ table: { resizable: false } }),
  Callout,
];

export interface WikiEditorProps {
  /** 최초 1회만 반영된다. 이후 변경은 무시 — uncontrolled다. */
  initialContent?: JSONContent;
  /** 마운트 후 바뀌어도 반영된다 — 아래 useEffect가 setEditable로 밀어 넣는다. */
  editable?: boolean;
  onUpdate?: (doc: JSONContent) => void;
  onContentError?: (error: Error) => void;
}

export default function WikiEditor({ initialContent, editable = true, onUpdate, onContentError }: WikiEditorProps) {
  // 콜백을 useEditor에 직접 넘기면 첫 렌더의 클로저가 영원히 호출된다 — 부모가 새 콜백을 넘겨도 갱신되지 않는다.
  // ref로 우회하고 커밋 후 갱신한다(콜백은 DOM 이벤트에서만 불린다).
  const onUpdateRef = useRef(onUpdate);
  const onContentErrorRef = useRef(onContentError);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
    onContentErrorRef.current = onContentError;
  }, [onUpdate, onContentError]);

  const [menu, setMenu] = useState<SlashMenuState | null>(null);
  const menuRef = useRef<SlashMenuHandle>(null);
  const [emojiMenu, setEmojiMenu] = useState<EmojiMenuState | null>(null);
  const emojiMenuRef = useRef<SlashMenuHandle>(null);

  // 메뉴가 닫혀 있으면(핸들 없음) 키를 소비하지 않는다.
  const handleMenuKeyDown = useCallback((event: KeyboardEvent) => menuRef.current?.onKeyDown(event) ?? false, []);
  const handleEmojiKeyDown = useCallback((event: KeyboardEvent) => emojiMenuRef.current?.onKeyDown(event) ?? false, []);

  // SlashCommand는 컴포넌트별 콜백을 물기 때문에 인스턴스마다 configure한다.
  const extensions = useMemo(
    () => [
      ...WIKI_EDITOR_EXTENSIONS,
      // react-hooks/refs 오탐: configure는 콜백을 저장만 하고 ref 접근은 키보드 이벤트 시점에만 일어난다.
      // eslint-disable-next-line react-hooks/refs
      SlashCommand.configure({
        onStateChange: setMenu,
        onKeyDown: handleMenuKeyDown,
      }),
      // eslint-disable-next-line react-hooks/refs -- 위와 동일한 오탐: 저장만 하고 이벤트 시점에 읽는다
      EmojiCommand.configure({
        onStateChange: setEmojiMenu,
        onKeyDown: handleEmojiKeyDown,
      }),
    ],
    [handleMenuKeyDown, handleEmojiKeyDown],
  );

  const editor = useEditor({
    extensions,
    content: initialContent,
    editable,
    // App Router는 서버에서 한 번 렌더된다. 즉시 렌더하면 hydration이 어긋난다.
    immediatelyRender: false,
    // 켜지 않으면 ProseMirror가 스키마에 없는 노드를 말없이 버린다.
    enableContentCheck: true,
    onContentError: ({ error }) => {
      console.error('[WikiEditor] 스키마에 없는 콘텐츠', error);
      onContentErrorRef.current?.(error);
    },
    onUpdate: ({ editor: instance }) => {
      onUpdateRef.current?.(instance.getJSON());
    },
  });

  // 옵션의 editable은 마운트 이후 무시되므로 직접 밀어 넣는다.
  // emitUpdate=false 필수 — true면 첫 글자를 치기 전에 onUpdate가 불려 부모가 즉시 "변경됨"이 된다.
  useEffect(() => {
    editor?.setEditable(editable, false);
  }, [editor, editable]);

  const rect = menu?.clientRect;

  return (
    <>
      {/* 본문 타이포그래피는 공용 markdown-reading.css(읽기 규격)를 재사용한다 — 빼면 preflight가 제목 크기를 지운다.
          아래 유틸은 두 마크다운 규격이 다루지 않는 것만 덮는다. */}
      <EditorContent
        editor={editor}
        className={[
          'markdown-body',
          'markdown-reading',
          'min-h-40',
          '[&_.ProseMirror]:outline-none',
          // 체크박스 목록: 마크다운 규격의 ul 마커·들여쓰기를 무효화하고 가로 배치
          '[&_ul[data-type=taskList]]:list-none [&_ul[data-type=taskList]]:pl-0',
          '[&_ul[data-type=taskList]_li]:flex [&_ul[data-type=taskList]_li]:items-start [&_ul[data-type=taskList]_li]:gap-2',
          '[&_ul[data-type=taskList]_li_>_label]:shrink-0 [&_ul[data-type=taskList]_li_>_div]:min-w-0 [&_ul[data-type=taskList]_li_>_div]:flex-1',
          // 콜아웃 — 마크다운 규격에 없는 블록
          '[&_div[data-type=callout]_>_*+*]:mt-2 [&_div[data-type=callout]_>_*:last-child]:mb-0',
          // 하이라이트 — 마크다운 규격에 없다 (구분선은 markdown-reading.css가 가진다)
          '[&_mark]:bg-fill-primary-normal-neutral [&_mark]:rounded-sm [&_mark]:px-0.5',
          // 표 격자 — 읽기 규격의 표는 행 구분선만 있다. 편집 중에는 셀 경계가 보여야 한다.
          '[&_td]:border [&_th]:border [&_td]:border-line-normal-normal [&_th]:border-line-normal-normal',
          '[&_th]:bg-fill-normal-strong',
        ].join(' ')}
      />
      <BlockDragHandle editor={editor} />
      {editor && editable && <FormattingToolbar editor={editor} />}

      {/* 커서에는 DOM 요소가 없다. 보이지 않는 anchor를 clientRect로 옮겨두면 Radix가 충돌 감지·플립을 맡는다. */}
      <Popover
        open={menu !== null}
        // 에디터 밖 클릭은 트랜잭션이 없어 Suggestion이 닫지 못한다 — 여기서 직접 닫지 않으면 메뉴가 뜬 채 남는다.
        onOpenChange={(open) => {
          if (!open) setMenu(null);
        }}
      >
        <PopoverAnchor asChild>
          <div
            aria-hidden
            className="pointer-events-none fixed"
            style={{
              top: rect?.top ?? 0,
              left: rect?.left ?? 0,
              width: rect?.width ?? 0,
              height: rect?.height ?? 0,
            }}
          />
        </PopoverAnchor>
        <PopoverContent
          align="start"
          side="bottom"
          className="w-auto border-none bg-transparent p-0 shadow-none"
          // 포커스는 에디터에 남아야 한다. 메뉴가 가져가면 타이핑이 끊긴다.
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          {menu && <SlashMenu ref={menuRef} items={menu.items} onSelect={menu.onSelect} />}
        </PopoverContent>
      </Popover>

      {/* `:` 이모지 서제스천 — 슬래시 메뉴와 같은 anchor 패턴의 별도 Popover */}
      <Popover
        open={emojiMenu !== null}
        onOpenChange={(open) => {
          if (!open) setEmojiMenu(null);
        }}
      >
        <PopoverAnchor asChild>
          <div
            aria-hidden
            className="pointer-events-none fixed"
            style={{
              top: emojiMenu?.clientRect?.top ?? 0,
              left: emojiMenu?.clientRect?.left ?? 0,
              width: emojiMenu?.clientRect?.width ?? 0,
              height: emojiMenu?.clientRect?.height ?? 0,
            }}
          />
        </PopoverAnchor>
        <PopoverContent
          align="start"
          side="bottom"
          className="w-auto border-none bg-transparent p-0 shadow-none"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          {emojiMenu && <EmojiMenu ref={emojiMenuRef} items={emojiMenu.items} onSelect={emojiMenu.onSelect} />}
        </PopoverContent>
      </Popover>
    </>
  );
}
