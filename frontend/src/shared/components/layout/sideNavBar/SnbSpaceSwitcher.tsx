'use client';

import { AnimatePresence, motion } from 'motion/react';

import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { layoutLabelFade, layoutLabelFadeReduced, layoutShiftTransition, MotionState } from '@/shared/motion';
import { cn } from '@/shared/utils/cn';

/** 홈·위키 SNB가 서로 교체돼도 같은 버튼으로 이어지게 하는 식별자 */
export const SPACE_SWITCHER_LAYOUT_ID = {
  home: 'snb-space-switcher-home',
  wiki: 'snb-space-switcher-wiki',
} as const;

export interface SnbSpaceSwitcherProps {
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  /** 닫힘과 미선택에서는 렌더하지 않고 aria-label로만 쓴다 */
  label: string;
  selected?: boolean;
  variant?: 'expanded' | 'closed';
  /** 주면 SNB가 갈려도 폭 전환이 이어진다. 같은 화면에 중복 id가 있으면 안 된다 */
  layoutId?: string;
  onClick?: () => void;
  className?: string;
}

/**
 * 홈 ↔ LLM Wiki 모드 스위처. 펼침에서는 선택된 쪽만 라벨을 드러내고 남은 폭을 차지하며,
 * 선택이 옮겨가면 두 버튼이 layout 전환으로 폭 비율을 주고받는다. 닫힘에서는 둘 다 정사각이다.
 */
export default function SnbSpaceSwitcher({
  Icon,
  label,
  selected = false,
  variant = 'expanded',
  layoutId,
  onClick,
  className,
}: SnbSpaceSwitcherProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const isClosed = variant === 'closed';
  const showsLabel = !isClosed && selected;
  // 닫힘은 폭이 변하지 않는 정사각이라 펼침에서만 layout 전환을 켠다
  const animatesLayout = !isClosed && !prefersReducedMotion;

  return (
    <motion.button
      type="button"
      layout={animatesLayout}
      // 스페이스를 옮기면 SNB가 통째로 갈린다 — 같은 id로 이어야 폭이 이어서 늘어난다
      layoutId={animatesLayout ? layoutId : undefined}
      transition={layoutShiftTransition}
      // rounded-full을 style로도 줘야(h-9의 절반) layout 스케일 중 모서리 왜곡을 motion이 보정한다
      style={isClosed ? undefined : { borderRadius: 18 }}
      onClick={onClick}
      aria-current={selected ? 'page' : undefined}
      // 라벨이 렌더되지 않을 때만 접근 이름을 따로 준다 — 둘 다 주면 중복으로 읽힌다
      aria-label={showsLabel ? undefined : label}
      className={cn(
        'flex h-9 cursor-pointer items-center justify-center gap-1.5 transition-colors',
        isClosed
          ? cn(
              'size-9 shrink-0 rounded-xl',
              selected
                ? 'border-line-normal-neutral bg-fill-normal-assistive shadow-card border'
                : 'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
            )
          : cn(
              'rounded-full',
              selected
                ? 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive min-w-0 flex-1 px-1.5 py-0.5'
                : 'bg-fill-normal-strong hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed shrink-0 px-5 py-1.5',
            ),
        className,
      )}
    >
      {/* layout="position"이 버튼 스케일을 상쇄해 아이콘·라벨이 늘어나 보이지 않는다 */}
      <motion.span layout={animatesLayout && 'position'} className="flex shrink-0 items-center justify-center">
        <Icon
          aria-hidden
          className={cn(
            'size-6',
            selected
              ? 'text-icon-normal-strong'
              : // 미선택 아이콘은 펼침에서 한 단계 더 옅다 — 선택 알약 옆에서 대비가 읽혀야 한다
                isClosed
                ? 'text-icon-normal-neutral'
                : 'text-icon-normal-alternative',
          )}
        />
      </motion.span>
      {/* popLayout이 나가는 라벨을 흐름에서 빼 줄어드는 쪽 폭이 한 번에 목표로 간다 */}
      <AnimatePresence initial={false} mode="popLayout">
        {showsLabel && (
          <motion.span
            key="label"
            layout={animatesLayout && 'position'}
            variants={prefersReducedMotion ? layoutLabelFadeReduced : layoutLabelFade}
            initial={MotionState.Hidden}
            animate={MotionState.Visible}
            exit={MotionState.Exit}
            className="text-heading-small text-text-normal-strong truncate"
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
