'use client';

import { forwardRef, useImperativeHandle, useState } from 'react';

import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from '@/shared/components/ui/command';

import type { SlashItem, SlashMenuHandle } from '../../types/llmWikiEditor';

/** 정의 순서를 유지하며 group별로 묶는다. 하이라이트 인덱스는 평평한 items 기준이라 그대로 둔다. */
function groupItems(items: readonly SlashItem[]): [string, SlashItem[]][] {
  const map = new Map<string, SlashItem[]>();
  for (const item of items) {
    const bucket = map.get(item.group);
    if (bucket) {
      bucket.push(item);
    } else {
      map.set(item.group, [item]);
    }
  }
  return [...map.entries()];
}

export interface SlashMenuProps {
  items: readonly SlashItem[];
  onSelect: (item: SlashItem) => void;
}

/**
 * 슬래시 메뉴 UI. Tiptap을 import하지 않는다 — 에디터 없이 스토리로 열린다.
 * 포커스가 ProseMirror에 있어 cmdk 키보드를 쓸 수 없다 — 하이라이트를 직접 들고 키는 onKeyDown 핸들로 받는다.
 */
const SlashMenu = forwardRef<SlashMenuHandle, SlashMenuProps>(function SlashMenu({ items, onSelect }, ref) {
  const [highlighted, setHighlighted] = useState(0);

  // 목록이 바뀌면 하이라이트를 처음으로 되돌린다 — 안 그러면 인덱스가 범위를 넘는다.
  // effect가 아니라 렌더 중 리셋(파생 상태 패턴)이다.
  const [prevItems, setPrevItems] = useState(items);
  if (items !== prevItems) {
    setPrevItems(items);
    setHighlighted(0);
  }

  useImperativeHandle(ref, () => ({
    onKeyDown: (event) => {
      if (items.length === 0) return false;

      // 한글 조합 중에는 Enter가 "조합 확정"이지 "항목 선택"이 아니다.
      if (event.isComposing) return false;

      if (event.key === 'ArrowDown') {
        setHighlighted((index) => (index + 1) % items.length);
        return true;
      }
      if (event.key === 'ArrowUp') {
        setHighlighted((index) => (index - 1 + items.length) % items.length);
        return true;
      }
      if (event.key === 'Enter') {
        const item = items[highlighted];
        if (item) onSelect(item);
        return true;
      }
      return false;
    },
  }));

  return (
    <Command
      shouldFilter={false}
      value={items[highlighted]?.id ?? ''}
      onValueChange={(value) => {
        const index = items.findIndex((item) => item.id === value);
        if (index >= 0) setHighlighted(index);
      }}
      className="border-line-normal-normal shadow-dropdown-menu w-70 rounded-2xl border"
    >
      <CommandList>
        <CommandEmpty>일치하는 블록이 없습니다</CommandEmpty>
        {groupItems(items).map(([group, groupedItems]) => (
          <CommandGroup key={group} heading={group}>
            {groupedItems.map((item) => (
              <CommandItem key={item.id} value={item.id} onSelect={() => onSelect(item)}>
                {item.Icon && <item.Icon aria-hidden className="text-icon-normal-normal size-6 shrink-0" />}
                <span className="flex min-w-0 flex-col">
                  <span className="text-text-normal-normal truncate">{item.label}</span>
                  {item.description && (
                    <span className="text-label-xsmall text-text-normal-alternative truncate">{item.description}</span>
                  )}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
    </Command>
  );
});

export default SlashMenu;
