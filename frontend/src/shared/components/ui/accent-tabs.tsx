'use client';

// violet 강조 톤 underline tab + 옵션 카운트 배지. 기본 톤은 underline-tabs.

import * as TabsPrimitive from '@radix-ui/react-tabs';
import { AnimatePresence, motion } from 'motion/react';

import { motionEase, MotionState } from '@/shared/motion/presets';
import { cn } from '@/shared/utils/cn';

const fastCountCrossfade = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.18, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.12, ease: motionEase } },
};

export interface AccentTabItem<V extends string = string> {
  value: V;
  label: string;
  // undefined면 배지 미렌더. 0은 그대로 표시(호출자가 표시 여부 결정).
  count?: number;
}

export interface AccentTabsProps<V extends string = string> {
  items: readonly AccentTabItem<V>[];
  value: V;
  onValueChange: (value: V) => void;
  ariaLabel: string;
  panelIdPrefix?: string;
  className?: string;
}

export default function AccentTabs<V extends string = string>({
  items,
  value,
  onValueChange,
  ariaLabel,
  panelIdPrefix,
  className,
}: AccentTabsProps<V>) {
  const panelKey = panelIdPrefix ?? 'accent-tab';

  return (
    <TabsPrimitive.Root value={value} onValueChange={(v) => onValueChange(v as V)}>
      <TabsPrimitive.List aria-label={ariaLabel} className={cn('flex items-center gap-5', className)}>
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            id={`tab-${panelKey}-${item.value}`}
            aria-controls={`tabpanel-${panelKey}-${item.value}`}
            className={cn(
              'group text-heading-small inline-flex cursor-pointer items-center gap-1.5 border-b-2 px-1 pb-2',
              'data-[state=active]:text-accent-violet-default data-[state=active]:border-accent-violet-default',
              'data-[state=inactive]:text-text-normal-alternative data-[state=inactive]:border-transparent',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={cn(
                  'text-body-xsmall rounded-md2 inline-flex h-5 min-w-5 items-center justify-center px-0.5',
                  'group-data-[state=active]:bg-accent-violet-default group-data-[state=active]:text-text-normal-inverse',
                  'group-data-[state=inactive]:bg-fill-normal-interaction-pressed group-data-[state=inactive]:text-text-normal-alternative',
                )}
                data-tab-state-badge
              >
                <AnimatePresence mode="popLayout" initial={false}>
                  <motion.span
                    key={item.count}
                    variants={fastCountCrossfade}
                    initial={MotionState.Hidden}
                    animate={MotionState.Visible}
                    exit={MotionState.Exit}
                  >
                    {item.count}
                  </motion.span>
                </AnimatePresence>
              </span>
            )}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
    </TabsPrimitive.Root>
  );
}
