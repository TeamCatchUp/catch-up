/**
 * 임베딩 동기화 기간 옵션 (한국어 라벨 기준).
 *
 * 컴포넌트(`PeriodSelect`)와 hook(`useChannelTalkSelection`), util(`channelTalkSyncDispatch`)
 * 세 레이어가 모두 참조하므로 components가 아닌 constants로 분리.
 * (이전엔 PeriodSelect.tsx에 있어 `utils → components` 역방향 import가 발생했음.)
 */
export const PERIOD_OPTIONS = ['1개월', '3개월', '6개월', '1년', '3년', '전체'] as const;

export type Period = (typeof PERIOD_OPTIONS)[number];

export const DEFAULT_PERIOD: Period = '전체';

export const isPeriod = (value: string): value is Period =>
  (PERIOD_OPTIONS as readonly string[]).includes(value);
