import type { Transition, Variants } from 'motion/react';

/**
 * Motion 디자인 토큰. CSS의 `--animate-duration-*` (animation.css)와 값을 동일하게 유지한다.
 * 변경 시 두 곳을 함께 갱신.
 */
export const motionDuration = {
  fast: 0.3,
  base: 0.5,
  slow: 0.7,
} as const;

/** cubic ease-in-out — fade-in/fade-out에 차분한 양방향 감속 곡선. */
export const motionEase = [0.42, 0, 0.58, 1] as const;

const baseTransition: Transition = {
  duration: motionDuration.base,
  ease: motionEase,
};

const fastTransition: Transition = {
  duration: motionDuration.fast,
  ease: motionEase,
};

/** 새 list item 등장(StepRow, plan step, chip 등)에 사용. */
export const fadeInUp: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: baseTransition },
  exit: { opacity: 0, transition: fastTransition },
};

/** 부모에 적용하면 자식 variants를 stagger 순서로 발화. */
export const staggerListContainer: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.05,
    },
  },
};

/** 펼침 디테일 박스 등장. AnimatePresence와 함께 사용해 마운트/언마운트를 부드럽게. */
export const collapseExpand: Variants = {
  hidden: { opacity: 0, height: 0 },
  visible: {
    opacity: 1,
    height: 'auto',
    transition: {
      ...baseTransition,
      height: { duration: motionDuration.base, ease: motionEase },
    },
  },
  exit: {
    opacity: 0,
    height: 0,
    transition: fastTransition,
  },
};

/** 두 요소 swap 시 opacity crossfade. AnimatePresence mode="wait"와 함께 사용. */
export const crossfade: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: baseTransition },
  exit: { opacity: 0, transition: fastTransition },
};

/** Typewriter — 텍스트를 word 단위 stagger로 등장. active step reasoning 등 토큰 흐름 표현용. */
export const typewriterWordsContainer: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.04,
    },
  },
};

export const typewriterWord: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      duration: motionDuration.fast,
      ease: motionEase,
    },
  },
};

export const MotionState = {
  Hidden: 'hidden',
  Visible: 'visible',
  Exit: 'exit',
} as const;

/** 패널 상태 swap(skeleton → empty/error/coming-soon 등)의 짧은 fade-in+up.
 *  motionDuration.fast(0.3) 보다 빠른 0.25/0.15 — 콘텐츠 등장이 아닌 상태 전환이라 더 빠른 체감이 자연스러움. */
export const panelStateFadeIn: Variants = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.15, ease: motionEase } },
};
