'use client';

import { type KeyboardEvent, useRef } from 'react';

import { cn } from '@/shared/utils/cn';

export interface UnderlineTabItem<V extends string = string> {
  value: V;
  label: string;
}

export interface UnderlineTabsProps<V extends string = string> {
  items: readonly UnderlineTabItem<V>[];
  value: V;
  onValueChange: (value: V) => void;
  ariaLabel: string;
  // tabpanel id 접두사. 기본값은 각 탭의 value
  panelIdPrefix?: string;
  className?: string;
}

export default function UnderlineTabs<V extends string = string>({
  items,
  value,
  onValueChange,
  ariaLabel,
  panelIdPrefix,
  className,
}: UnderlineTabsProps<V>) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const panelKey = panelIdPrefix ?? 'underline-tab';

  const focusTab = (index: number) => {
    const next = items[index];
    if (!next) return;
    onValueChange(next.value);
    tabRefs.current[index]?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        focusTab(index === 0 ? items.length - 1 : index - 1);
        return;
      case 'ArrowRight':
        e.preventDefault();
        focusTab(index === items.length - 1 ? 0 : index + 1);
        return;
      case 'Home':
        e.preventDefault();
        focusTab(0);
        return;
      case 'End':
        e.preventDefault();
        focusTab(items.length - 1);
        return;
      default:
        return;
    }
  };

  return (
    <div role="tablist" aria-label={ariaLabel} className={cn('flex items-center gap-6', className)}>
      {items.map((item, index) => {
        const isActive = item.value === value;
        return (
          <button
            key={item.value}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${panelKey}-${item.value}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${panelKey}-${item.value}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onValueChange(item.value)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={cn(
              'text-heading-large cursor-pointer border-b-[3px] px-0.5 pb-1.25',
              isActive ? 'text-content-normal border-edge-strong' : 'text-content-assistive border-transparent',
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
