'use client';

import { forwardRef, useImperativeHandle, useState } from 'react';

import { Command, CommandEmpty, CommandItem, CommandList } from '@/shared/components/ui/command';

import type { EmojiItem, SlashMenuHandle } from '../../types/llmWikiEditor';

export interface EmojiMenuProps {
  items: readonly EmojiItem[];
  onSelect: (item: EmojiItem) => void;
}

/**
 * `:` 이모지 서제스천 메뉴. SlashMenu와 같은 구조지만 글리프가 SVG가 아니라 이모지 문자라
 * 재사용하지 않고 얇게 분리했다.
 */
const EmojiMenu = forwardRef<SlashMenuHandle, EmojiMenuProps>(function EmojiMenu({ items, onSelect }, ref) {
  const [highlighted, setHighlighted] = useState(0);

  const [prevItems, setPrevItems] = useState(items);
  if (items !== prevItems) {
    setPrevItems(items);
    setHighlighted(0);
  }

  useImperativeHandle(ref, () => ({
    onKeyDown: (event) => {
      if (items.length === 0) return false;
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
      value={items[highlighted]?.name ?? ''}
      onValueChange={(value) => {
        const index = items.findIndex((item) => item.name === value);
        if (index >= 0) setHighlighted(index);
      }}
      className="border-line-normal-normal shadow-dropdown-menu w-56 rounded-2xl border"
    >
      <CommandList>
        <CommandEmpty>일치하는 이모지가 없습니다</CommandEmpty>
        {items.map((item) => (
          <CommandItem key={item.name} value={item.name} onSelect={() => onSelect(item)}>
            <span aria-hidden className="w-6 shrink-0 text-center">
              {item.emoji}
            </span>
            <span className="text-text-normal-normal truncate">:{item.name}:</span>
          </CommandItem>
        ))}
      </CommandList>
    </Command>
  );
});

export default EmojiMenu;
