'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { EditorContent, type JSONContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

import { Popover, PopoverAnchor, PopoverContent } from '@/shared/components/ui/popover';

import type { SlashMenuHandle, SlashMenuState } from '../../types/llmWikiEditor';
import BlockDragHandle from './BlockDragHandle';
import { SlashCommand } from './extensions/slashCommand';
import { WikiBlockAttrs } from './extensions/wikiBlockAttrs';
import SlashMenu from './SlashMenu';

/** WikiEditor가 쓰는 확장 목록. 테스트가 같은 목록으로 왕복을 검증한다 — 배열에서 확장을 빼면 그 테스트가 깨진다. */
export const WIKI_EDITOR_EXTENSIONS = [StarterKit, WikiBlockAttrs];

export interface WikiEditorProps {
  /** 최초 1회만 반영된다. 이후 변경은 무시 — uncontrolled다. */
  initialContent?: JSONContent;
  /** 마운트 후 바뀌어도 반영된다 — 아래 useEffect가 setEditable로 밀어 넣는다. */
  editable?: boolean;
  onUpdate?: (doc: JSONContent) => void;
  onContentError?: (error: Error) => void;
}

export default function WikiEditor({ initialContent, editable = true, onUpdate, onContentError }: WikiEditorProps) {
  // Editor 생성자가 this.on('update', this.options.onUpdate)로 함수 참조를 그대로 등록하고,
  // useEditor의 옵션 비교는 핸들러 키를 제외한다. 콜백을 직접 넘기면 첫 렌더의 클로저가
  // 영원히 호출된다 — 부모가 새 콜백을 넘겨도 갱신되지 않는다. 그래서 ref로 우회한다.
  // 렌더 중 ref를 쓰면 react-hooks/refs가 막는다(그리고 concurrent 렌더에서 실제로 위험하다).
  // 커밋 후 갱신해도 되는 이유: 이 콜백들은 DOM 이벤트에서만 불리고, DOM 이벤트는 커밋 뒤에 온다.
  const onUpdateRef = useRef(onUpdate);
  const onContentErrorRef = useRef(onContentError);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
    onContentErrorRef.current = onContentError;
  }, [onUpdate, onContentError]);

  const [menu, setMenu] = useState<SlashMenuState | null>(null);
  const menuRef = useRef<SlashMenuHandle>(null);

  // 메뉴가 닫혀 있으면(핸들 없음) 키를 소비하지 않는다.
  const handleMenuKeyDown = useCallback((event: KeyboardEvent) => menuRef.current?.onKeyDown(event) ?? false, []);

  // SlashCommand는 컴포넌트별 콜백(setMenu·menuRef)을 물기 때문에 인스턴스마다 configure한다.
  // setMenu(useState setter)·handleMenuKeyDown은 identity가 안정적이라 1회 생성으로 충분하다.
  const extensions = useMemo(
    () => [
      ...WIKI_EDITOR_EXTENSIONS,
      // react-hooks/refs 오탐: configure는 콜백을 저장만 하고(Extension options), menuRef.current
      // 접근은 Suggestion onKeyDown 즉 키보드 이벤트 시점에만 일어난다 — 렌더 중 읽기 경로가 없다.
      // eslint-disable-next-line react-hooks/refs
      SlashCommand.configure({
        onStateChange: setMenu,
        onKeyDown: handleMenuKeyDown,
      }),
    ],
    [handleMenuKeyDown],
  );

  const editor = useEditor({
    extensions,
    content: initialContent,
    editable,
    // App Router는 서버에서 한 번 렌더된다. 즉시 렌더하면 hydration이 어긋난다.
    immediatelyRender: false,
    // 켜지 않으면 ProseMirror가 스키마에 없는 노드를 말없이 버린다.
    // 지금은 픽스처만 넣어 티가 안 나지만, blocks[]가 들어올 때 claim_section이
    // 사라지고도 화면은 멀쩡해 보인다.
    enableContentCheck: true,
    onContentError: ({ error }) => {
      console.error('[WikiEditor] 스키마에 없는 콘텐츠', error);
      onContentErrorRef.current?.(error);
    },
    onUpdate: ({ editor: instance }) => {
      onUpdateRef.current?.(instance.getJSON());
    },
  });

  // useEditor는 deps 없이 리렌더되면 editable을 현재 에디터 값으로 되돌린다.
  // 즉 옵션에 넘긴 editable은 마운트 이후 무시된다 — 여기서 직접 밀어 넣어야 반응한다.
  // 두 번째 인자 emitUpdate는 기본값이 true다. immediatelyRender: false라 editor는 두 번째
  // 렌더에 생기고, 이 effect는 반드시 한 번 돈다 — 그대로 두면 사용자가 한 글자도 치기 전에
  // onUpdate(초기 문서)가 불려서 부모의 dirty 추적·autosave가 마운트 직후 "변경됨"이 된다.
  // false여도 setOptions가 view.updateState까지 하므로 editable 변경 자체는 적용된다.
  useEffect(() => {
    editor?.setEditable(editable, false);
  }, [editor, editable]);

  const rect = menu?.clientRect;

  return (
    <>
      <EditorContent editor={editor} className="min-h-40" />
      <BlockDragHandle editor={editor} />

      {/*
        커서에는 DOM 요소가 없다. 보이지 않는 anchor를 clientRect 좌표로 옮겨두면
        Radix가 충돌 감지·플립·포탈을 알아서 한다. top/left를 직접 계산하면
        메뉴가 화면 아래에서 잘린다.
      */}
      <Popover open={menu !== null}>
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
    </>
  );
}
