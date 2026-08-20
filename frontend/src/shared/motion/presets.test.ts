import type { TargetAndTransition, Variant, Variants } from 'motion/react';
import { describe, expect, it } from 'vitest';

import {
  disclosureExpand,
  disclosureExpandReduced,
  panelStateFadeIn,
  panelStateFadeInReduced,
  stepReplace,
  stepReplaceReduced,
} from './presets';

/** 변형이 함수형(custom 의존)이면 방향을 넣어 풀고, 아니면 그대로 쓴다 */
const resolve = (variant: Variant | undefined, direction = 1): TargetAndTransition =>
  typeof variant === 'function'
    ? (variant(direction, {}, {}) as TargetAndTransition)
    : ((variant ?? {}) as TargetAndTransition);

const states = (variants: Variants, direction = 1) => ({
  hidden: resolve(variants.hidden, direction),
  visible: resolve(variants.visible, direction),
  exit: resolve(variants.exit, direction),
});

/** 공간 이동을 뜻하는 키. reduced 변형에는 하나도 남으면 안 된다 */
const SPATIAL_KEYS = ['x', 'y', 'z', 'scale', 'rotate', 'translateX', 'translateY'] as const;

describe('stepReplace', () => {
  it('방향에 따라 들어오는 쪽과 나가는 쪽이 뒤집힌다', () => {
    const forward = states(stepReplace, 1);
    const backward = states(stepReplace, -1);

    // 다음 항목은 아래에서 들어와 위로 나간다. 이전 항목은 그 반대다
    expect(forward.hidden.y).toBeGreaterThan(0);
    expect(forward.exit.y).toBeLessThan(0);
    expect(backward.hidden.y).toBe(-(forward.hidden.y as number));
    expect(backward.exit.y).toBe(-(forward.exit.y as number));

    // 안착 상태에는 이동이 남지 않는다
    expect(forward.visible.y).toBe(0);
  });

  it('나가는 쪽이 들어오는 쪽보다 짧다 — mode="wait"에서 총 시간이 늘어지지 않게', () => {
    const { visible, exit } = states(stepReplace);

    expect(exit.transition?.duration).toBeLessThan(visible.transition?.duration as number);
  });
});

describe('reduced motion 변형', () => {
  it('교체 전환에서 공간 이동을 전부 뺀다', () => {
    for (const variants of [stepReplaceReduced, panelStateFadeInReduced]) {
      for (const state of Object.values(states(variants))) {
        for (const key of SPATIAL_KEYS) expect(state).not.toHaveProperty(key);
      }
    }
  });

  it('교체 전환에는 상태 연속성을 지킬 만큼의 짧은 opacity fade만 남긴다', () => {
    const reduced = states(stepReplaceReduced);
    const normal = states(stepReplace);

    expect(reduced.hidden.opacity).toBe(0);
    expect(reduced.visible.opacity).toBe(1);
    expect(reduced.visible.transition?.duration).toBeLessThanOrEqual(normal.visible.transition?.duration as number);
  });

  it('접기·펼치기는 애니메이션 없이 즉시 반영한다', () => {
    for (const state of Object.values(states(disclosureExpandReduced))) {
      expect(state.transition?.duration).toBe(0);
    }
    // 원본은 실제로 시간을 쓴다 — 비교 대상이 없으면 위 어서션이 공허해진다
    expect(states(disclosureExpand).visible.transition?.duration).toBeGreaterThan(0);
  });

  it('패널 상태 교체의 y 오프셋이 reduced에서만 사라진다', () => {
    expect(states(panelStateFadeIn).hidden.y).toBeGreaterThan(0);
    expect(states(panelStateFadeInReduced).hidden).not.toHaveProperty('y');
  });
});
