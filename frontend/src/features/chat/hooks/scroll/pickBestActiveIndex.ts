/**
 * viewport 중심에 가장 가까운 페어 인덱스를 선정. hysteresis로 잦은 변경을 막는다.
 * ratio 가드를 쓰지 않는 이유: 페어 height가 viewport보다 크면 ratio가 항상 작아져 모든 후보가 걸러짐.
 * @returns 변경할 새 인덱스, 변경 불필요하면 null.
 */
export interface PickBestActiveIndexParams {
  observedEntries: Map<number, { boundingClientRect: { top: number; height: number } }>;
  rootRect: { top: number; height: number };
  currentIdx: number;
  hysteresisPx: number;
}

export const pickBestActiveIndex = ({
  observedEntries,
  rootRect,
  currentIdx,
  hysteresisPx,
}: PickBestActiveIndexParams): number | null => {
  if (observedEntries.size === 0) return null;

  const viewportCenter = rootRect.top + rootRect.height / 2;

  let bestIdx = -1;
  let bestDistance = Number.POSITIVE_INFINITY;

  for (const [idx, entry] of observedEntries) {
    const { top, height } = entry.boundingClientRect;
    const pairCenter = top + height / 2;
    const distance = Math.abs(pairCenter - viewportCenter);

    if (distance < bestDistance) {
      bestDistance = distance;
      bestIdx = idx;
    }
  }

  if (bestIdx < 0 || bestIdx === currentIdx) return null;

  const currentEntry = observedEntries.get(currentIdx);
  let currentDistance = Number.POSITIVE_INFINITY;

  if (currentEntry) {
    const { top, height } = currentEntry.boundingClientRect;
    const currentCenter = top + height / 2;
    currentDistance = Math.abs(currentCenter - viewportCenter);
  }

  const shouldSwitch = !Number.isFinite(currentDistance) || bestDistance + hysteresisPx < currentDistance;

  return shouldSwitch ? bestIdx : null;
};
