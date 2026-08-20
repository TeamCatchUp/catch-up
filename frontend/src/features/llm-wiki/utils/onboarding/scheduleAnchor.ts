import { formatISO, setHours, startOfDay } from 'date-fns';

/** 알 수 없는 선택값이 오면 떨어질 자리. 매일·자정은 일정 필드의 기본 선택과 같다 */
export const DEFAULT_INTERVAL_MINUTES = 1440;
export const DEFAULT_ANCHOR_HOUR = 0;

/** 키는 SCHEDULE_FIELDS의 갱신 주기 옵션 id다 */
const INTERVAL_MINUTES_BY_OPTION_ID: Readonly<Record<string, number>> = {
  '6h': 360,
  '12h': 720,
  daily: DEFAULT_INTERVAL_MINUTES,
  weekly: 10080,
};

/** 키는 SCHEDULE_FIELDS의 실행 시각 옵션 id다 */
const ANCHOR_HOUR_BY_OPTION_ID: Readonly<Record<string, number>> = {
  midnight: DEFAULT_ANCHOR_HOUR,
  '6am': 6,
  noon: 12,
  '6pm': 18,
};

export function intervalMinutesOf(pollingOptionId: string | undefined): number {
  return INTERVAL_MINUTES_BY_OPTION_ID[pollingOptionId ?? ''] ?? DEFAULT_INTERVAL_MINUTES;
}

/**
 * 오늘 날짜 + 고른 시각을 타임존 포함 ISO로 만든다. 과거여도 앞으로 밀지 않는다 —
 * 앵커는 시작이 아니라 위상이라, 옮기면 "6시간마다"가 00·06·12·18에서 어긋난다.
 */
export function buildExecutionAnchor(runTimeOptionId: string | undefined, now: Date): string {
  const hour = ANCHOR_HOUR_BY_OPTION_ID[runTimeOptionId ?? ''] ?? DEFAULT_ANCHOR_HOUR;
  return formatISO(setHours(startOfDay(now), hour));
}

/**
 * APScheduler interval 트리거가 잡는 첫 실행 시각.
 * 앵커가 미래면 앵커 그대로, 과거면 앵커 + interval × ceil((now − 앵커) / interval)이다.
 */
export function resolveNextRunAt(anchorIso: string, intervalMinutes: number, now: Date): Date {
  const anchor = new Date(anchorIso);
  const intervalMs = (intervalMinutes > 0 ? intervalMinutes : DEFAULT_INTERVAL_MINUTES) * 60_000;

  if (anchor.getTime() > now.getTime()) return anchor;

  const periods = Math.ceil((now.getTime() - anchor.getTime()) / intervalMs);
  return new Date(anchor.getTime() + periods * intervalMs);
}
