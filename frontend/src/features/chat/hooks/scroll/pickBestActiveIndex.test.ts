import { describe, expect, it } from 'vitest';

import { pickBestActiveIndex } from './pickBestActiveIndex';

interface FakeEntry {
  boundingClientRect: { top: number; height: number };
}

const buildEntries = (entries: Array<{ idx: number; top: number; height: number }>) => {
  const map = new Map<number, FakeEntry>();
  for (const e of entries) {
    map.set(e.idx, { boundingClientRect: { top: e.top, height: e.height } });
  }
  return map;
};

const HYSTERESIS_PX = 48;

describe('pickBestActiveIndex', () => {
  it('빈 candidates면 null 반환', () => {
    const result = pickBestActiveIndex({
      observedEntries: new Map(),
      rootRect: { top: 0, height: 600 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    expect(result).toBeNull();
  });

  it('best match가 currentIdx와 같으면 null 반환', () => {
    const entries = buildEntries([{ idx: 0, top: 0, height: 600 }]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 0, height: 600 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    expect(result).toBeNull();
  });

  it('viewport 중심에 가장 가까운 페어 인덱스 반환', () => {
    // viewport: top=0, height=600, center=300
    // 페어 0: top=-100, height=200, center=0 (거리 300)
    // 페어 1: top=200, height=200, center=300 (거리 0)
    const entries = buildEntries([
      { idx: 0, top: -100, height: 200 },
      { idx: 1, top: 200, height: 200 },
    ]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 0, height: 600 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    expect(result).toBe(1);
  });

  it('hysteresis: 새 best가 current보다 hysteresis만큼 더 가깝지 않으면 switch 안 함', () => {
    // viewport: center=300
    // 페어 0 (current): top=100, height=200, center=200 (거리 100)
    // 페어 1: top=300, height=200, center=400 (거리 100) — current와 동일 거리
    const entries = buildEntries([
      { idx: 0, top: 100, height: 200 },
      { idx: 1, top: 300, height: 200 },
    ]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 0, height: 600 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    // bestDistance(100) + hysteresis(48) = 148 < currentDistance(100)? false → null
    expect(result).toBeNull();
  });

  it('hysteresis: 새 best가 hysteresis 이상 더 가까우면 switch', () => {
    // viewport: center=300
    // 페어 0 (current): top=-200, height=100, center=-150 (거리 450)
    // 페어 1: top=250, height=100, center=300 (거리 0)
    const entries = buildEntries([
      { idx: 0, top: -200, height: 100 },
      { idx: 1, top: 250, height: 100 },
    ]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 0, height: 600 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    // 0 + 48 = 48 < 450 → true → switch
    expect(result).toBe(1);
  });

  it('current가 candidates에 없으면 무조건 best로 switch', () => {
    // viewport: center=300
    // currentIdx=99 (없음)
    // 페어 0: top=200, height=200, center=300 (거리 0)
    const entries = buildEntries([{ idx: 0, top: 200, height: 200 }]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 0, height: 600 },
      currentIdx: 99,
      hysteresisPx: HYSTERESIS_PX,
    });
    expect(result).toBe(0);
  });

  it('🎯 핵심: 페어 height가 viewport보다 훨씬 커도 active 후보로 인정', () => {
    // 실제 라이브 진단 케이스 재현:
    //   viewport: top=52, height=633, center=368.5
    //   페어 0: bottom=-2716, top=-8292, height=5576 → center=-5504 (viewport 위)
    //   페어 1: top=-2668, height=6072, bottom=3404 → center=368
    // 페어 1이 viewport 중심과 거의 일치 (거리 0.5).
    // 페어 0은 멀리 위 (거리 5872).
    // 기대: bestIdx = 1
    const entries = buildEntries([
      { idx: 0, top: -8292, height: 5576 },
      { idx: 1, top: -2668, height: 6072 },
    ]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 52, height: 633 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    expect(result).toBe(1);
  });

  it('🎯 핵심: 페어 height >> viewport, 페어 0이 viewport 중심에 위치하면 0 유지', () => {
    // mount 직후, scrollTop=0:
    //   viewport: top=52, height=633, center=368.5
    //   페어 0: top=125, height=5576, bottom=5701 → center=2913 (viewport 한참 아래)
    //   페어 1: top=5749, height=6072, bottom=11821 → center=8785 (더 아래)
    // 페어 0의 center가 viewport center와 더 가까움
    const entries = buildEntries([
      { idx: 0, top: 125, height: 5576 },
      { idx: 1, top: 5749, height: 6072 },
    ]);
    const result = pickBestActiveIndex({
      observedEntries: entries,
      rootRect: { top: 52, height: 633 },
      currentIdx: 0,
      hysteresisPx: HYSTERESIS_PX,
    });
    // bestIdx=0, currentIdx=0 → null (변경 없음)
    expect(result).toBeNull();
  });
});
