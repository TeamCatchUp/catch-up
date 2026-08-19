import { describe, expect, it } from 'vitest';

import { SCHEDULE_FIELD_IDS, SCHEDULE_FIELDS } from '../../fixtures/llmWikiOnboardingFixtures';
import { buildExecutionAnchor, DEFAULT_INTERVAL_MINUTES, intervalMinutesOf, resolveNextRunAt } from './scheduleAnchor';

// 2026-08-19(수) 13:00 로컬. 타임존 오프셋을 고정하지 않으려고 로컬 생성자를 쓴다
const NOW = new Date(2026, 7, 19, 13, 0, 0);
const MINUTE_MS = 60_000;

const optionIdsOf = (fieldId: string) =>
  SCHEDULE_FIELDS.find((field) => field.id === fieldId)?.options?.map((option) => option.id) ?? [];

describe('intervalMinutesOf', () => {
  it('주기 선택지를 APScheduler interval 분으로 옮긴다', () => {
    expect(intervalMinutesOf('6h')).toBe(360);
    expect(intervalMinutesOf('12h')).toBe(720);
    expect(intervalMinutesOf('daily')).toBe(1440);
    expect(intervalMinutesOf('weekly')).toBe(10080);
  });

  it('픽스처의 주기 옵션 id를 모두 안다', () => {
    for (const optionId of optionIdsOf(SCHEDULE_FIELD_IDS.pollingInterval)) {
      expect(intervalMinutesOf(optionId)).toBeGreaterThan(0);
    }
  });

  it('없거나 모르는 값은 매일로 떨어진다 — 던지지 않는다', () => {
    expect(intervalMinutesOf(undefined)).toBe(DEFAULT_INTERVAL_MINUTES);
    expect(intervalMinutesOf('every-minute')).toBe(DEFAULT_INTERVAL_MINUTES);
  });
});

describe('buildExecutionAnchor', () => {
  it('오늘 날짜 + 고른 시각이고 타임존이 붙는다', () => {
    const anchor = buildExecutionAnchor('6pm', NOW);

    expect(anchor).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)$/);
    expect(new Date(anchor).getHours()).toBe(18);
    expect(new Date(anchor).getDate()).toBe(NOW.getDate());
  });

  it('이미 지난 시각이어도 오늘로 둔다 — 앵커는 시작이 아니라 위상이다', () => {
    const anchor = new Date(buildExecutionAnchor('midnight', NOW));

    expect(anchor.getTime()).toBeLessThan(NOW.getTime());
    expect(anchor.getHours()).toBe(0);
    expect(anchor.getDate()).toBe(NOW.getDate());
  });

  it('픽스처의 실행 시각 옵션 id를 모두 안다 — 자정 기본값과 겹치지 않는다', () => {
    const hours = optionIdsOf(SCHEDULE_FIELD_IDS.runTime).map((id) =>
      new Date(buildExecutionAnchor(id, NOW)).getHours(),
    );

    expect(hours).toEqual([0, 6, 12, 18]);
  });

  it('없거나 모르는 값은 자정으로 떨어진다 — 던지지 않는다', () => {
    expect(new Date(buildExecutionAnchor(undefined, NOW)).getHours()).toBe(0);
    expect(new Date(buildExecutionAnchor('3am', NOW)).getHours()).toBe(0);
  });
});

describe('resolveNextRunAt', () => {
  it('앵커가 미래면 앵커가 곧 첫 실행이다', () => {
    const anchor = buildExecutionAnchor('6pm', NOW);

    expect(resolveNextRunAt(anchor, 1440, NOW).getTime()).toBe(new Date(anchor).getTime());
  });

  it('6시간마다: 자정 앵커에 13시면 다음 경계는 오늘 18시다', () => {
    const next = resolveNextRunAt(buildExecutionAnchor('midnight', NOW), 360, NOW);

    expect(next.getDate()).toBe(NOW.getDate());
    expect(next.getHours()).toBe(18);
  });

  it('12시간마다: 자정 앵커에 13시면 다음 경계는 내일 자정이다', () => {
    const next = resolveNextRunAt(buildExecutionAnchor('midnight', NOW), 720, NOW);

    expect(next.getDate()).toBe(NOW.getDate() + 1);
    expect(next.getHours()).toBe(0);
  });

  it('매일: 자정 앵커에 13시면 내일 자정이다', () => {
    const next = resolveNextRunAt(buildExecutionAnchor('midnight', NOW), 1440, NOW);

    expect(next.getDate()).toBe(NOW.getDate() + 1);
    expect(next.getHours()).toBe(0);
  });

  it('주 1회: 자정 앵커에 13시면 7일 뒤 같은 요일 자정이다', () => {
    const anchor = buildExecutionAnchor('midnight', NOW);
    const next = resolveNextRunAt(anchor, 10080, NOW);

    expect(next.getTime() - new Date(anchor).getTime()).toBe(7 * 24 * 60 * MINUTE_MS);
    expect(next.getDay()).toBe(NOW.getDay());
  });

  it('오전 6시 앵커 + 6시간마다는 오전 6시가 아니라 위상이 맞는 경계로 간다', () => {
    const next = resolveNextRunAt(buildExecutionAnchor('6am', NOW), 360, NOW);

    expect(next.getHours()).toBe(18);
  });

  it('주기가 0 이하로 들어와도 매일로 떨어진다 — 나눗셈이 무한대로 가지 않는다', () => {
    const next = resolveNextRunAt(buildExecutionAnchor('midnight', NOW), 0, NOW);

    expect(next.getDate()).toBe(NOW.getDate() + 1);
    expect(next.getHours()).toBe(0);
  });
});
