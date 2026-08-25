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

/** 사이드바 메뉴·아코디언 등 클릭 즉시 반응해야 하는 접기/펴기.
 *  collapseExpand(0.5)는 콘텐츠 등장용이라 토글 조작에는 굼뜨게 느껴진다.
 *  적용 대상에 반드시 overflow-hidden을 함께 준다 — height 축소 중 자식이 밖으로 나온다. */
export const disclosureExpand: Variants = {
  hidden: { opacity: 0, height: 0 },
  visible: {
    opacity: 1,
    height: 'auto',
    transition: { duration: 0.2, ease: motionEase },
  },
  exit: {
    opacity: 0,
    height: 0,
    transition: { duration: 0.15, ease: motionEase },
  },
};

/** disclosureExpand의 reduced-motion 변형. 높이 변화를 애니메이션 없이 즉시 반영한다.
 *  usePrefersReducedMotion()이 true일 때 호출부가 이쪽으로 교체한다. */
export const disclosureExpandReduced: Variants = {
  hidden: { opacity: 0, height: 0, transition: { duration: 0 } },
  visible: { opacity: 1, height: 'auto', transition: { duration: 0 } },
  exit: { opacity: 0, height: 0, transition: { duration: 0 } },
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

/** 교체 전환의 이동 거리(px). 방향만 읽히면 되는 값이라 행 높이보다 작게 잡는다. */
const STEP_REPLACE_SHIFT = 12;

/** 순서가 있는 항목 사이를 오갈 때 내용 전체가 교체되는 전환.
 *  custom에 1(다음)·-1(이전)을 주면 그 방향으로 들어오고 반대로 나간다. */
export const stepReplace: Variants = {
  hidden: (direction: number = 1) => ({ opacity: 0, y: direction * STEP_REPLACE_SHIFT }),
  visible: { opacity: 1, y: 0, transition: { duration: 0.22, ease: motionEase } },
  exit: (direction: number = 1) => ({
    opacity: 0,
    y: direction * -STEP_REPLACE_SHIFT,
    transition: { duration: 0.12, ease: motionEase },
  }),
};

/** 교체 전환의 reduced-motion 형태. 공간 이동을 빼고 상태 연속성을 지킬 만큼의 fade만 남긴다. */
const reducedReplaceFade: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.12, ease: motionEase } },
  exit: { opacity: 0, transition: { duration: 0.08, ease: motionEase } },
};

/** stepReplace의 reduced-motion 변형. usePrefersReducedMotion()이 true일 때 호출부가 이쪽으로 교체한다. */
export const stepReplaceReduced: Variants = reducedReplaceFade;

/** crossfade의 reduced-motion 변형. 위와 같은 이유로 짧은 fade만 남긴다. */
export const crossfadeReduced: Variants = reducedReplaceFade;

/** panelStateFadeIn의 reduced-motion 변형. 위와 같은 이유로 y를 뺀다. */
export const panelStateFadeInReduced: Variants = reducedReplaceFade;
