'use client';

// 기본 중립 톤 underline tab. 강조 톤이 필요하면 accent-tabs 사용.

import * as TabsPrimitive from '@radix-ui/react-tabs';

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
  // tabpanel id 접두사. 기본값은 'underline-tab'
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
  const panelKey = panelIdPrefix ?? 'underline-tab';

  return (
    <TabsPrimitive.Root value={value} onValueChange={(v) => onValueChange(v as V)}>
      <TabsPrimitive.List aria-label={ariaLabel} className={cn('flex items-center gap-6', className)}>
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            id={`tab-${panelKey}-${item.value}`}
            aria-controls={`tabpanel-${panelKey}-${item.value}`}
            className={cn(
              'text-heading-large cursor-pointer border-b-[3px] px-0.5 pb-1.25',
              'data-[state=active]:text-text-normal-normal data-[state=active]:border-line-normal-strong',
              'data-[state=inactive]:text-text-normal-assistive data-[state=inactive]:border-transparent',
            )}
          >
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
    </TabsPrimitive.Root>
  );
}
