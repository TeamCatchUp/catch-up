import { describe, expect, it } from 'vitest';

import { ONBOARDING_APPROVAL_PRINCIPLE_TEXT } from '../../fixtures/llmWikiOnboardingFixtures';
import { buildOnboardingNextSteps, formatNextRunLabel } from './onboardingNextSteps';
import { buildExecutionAnchor, intervalMinutesOf, resolveNextRunAt } from './scheduleAnchor';

// 2026-08-19(수) 13:00 로컬
const NOW = new Date(2026, 7, 19, 13, 0, 0);

const nextRunFor = (pollingOptionId: string, runTimeOptionId: string) =>
  resolveNextRunAt(buildExecutionAnchor(runTimeOptionId, NOW), intervalMinutesOf(pollingOptionId), NOW);

describe('formatNextRunLabel', () => {
  it('같은 날이면 "오늘"이다', () => {
    expect(formatNextRunLabel(new Date(2026, 7, 19, 18, 0, 0), NOW)).toBe('오늘 오후 6시');
  });

  it('자정과 정오는 시각 대신 이름으로 부른다', () => {
    expect(formatNextRunLabel(new Date(2026, 7, 20, 0, 0, 0), NOW)).toBe('내일 자정');
    expect(formatNextRunLabel(new Date(2026, 7, 20, 12, 0, 0), NOW)).toBe('내일 정오');
  });

  it('7일 뒤는 다음 주 같은 요일이다', () => {
    expect(formatNextRunLabel(new Date(2026, 7, 26, 6, 0, 0), NOW)).toBe('다음 주 수요일 오전 6시');
  });

  it('그 밖의 날짜는 월·일로 적는다', () => {
    expect(formatNextRunLabel(new Date(2026, 8, 1, 6, 0, 0), NOW)).toBe('9월 1일 오전 6시');
  });
});

describe('buildOnboardingNextSteps', () => {
  it('기본 선택(매일·자정)이면 "내일 자정"이다', () => {
    const steps = buildOnboardingNextSteps({
      backfillOptionId: 'from-now',
      nextRunAt: nextRunFor('daily', 'midnight'),
      now: NOW,
    });

    expect(steps[0]).toBe('오늘 들어오는 상담부터 수집을 시작해요');
    expect(steps[1]).toBe('내일 자정 첫 갱신 때 첫 문서 초안이 검토 큐에 도착해요');
  });

  it('6시간마다·오전 6시를 고르면 "내일 자정"이라고 말하지 않는다', () => {
    const steps = buildOnboardingNextSteps({
      backfillOptionId: 'from-now',
      nextRunAt: nextRunFor('6h', '6am'),
      now: NOW,
    });

    expect(steps[1]).toBe('오늘 오후 6시 첫 갱신 때 첫 문서 초안이 검토 큐에 도착해요');
  });

  it('주 1회를 고르면 다음 주로 간다', () => {
    const steps = buildOnboardingNextSteps({
      backfillOptionId: 'from-now',
      nextRunAt: nextRunFor('weekly', 'midnight'),
      now: NOW,
    });

    expect(steps[1]).toBe('다음 주 수요일 자정 첫 갱신 때 첫 문서 초안이 검토 큐에 도착해요');
  });

  it('백필 선택이 바뀌면 첫 줄이 따라간다', () => {
    const steps = buildOnboardingNextSteps({
      backfillOptionId: 'all',
      nextRunAt: nextRunFor('daily', 'midnight'),
      now: NOW,
    });

    expect(steps[0]).toBe('지금까지 쌓인 상담 전체부터 수집을 시작해요');
  });

  it('모르는 백필 값은 "지금부터" 문구로 떨어진다', () => {
    const steps = buildOnboardingNextSteps({
      backfillOptionId: undefined,
      nextRunAt: nextRunFor('daily', 'midnight'),
      now: NOW,
    });

    expect(steps[0]).toBe('오늘 들어오는 상담부터 수집을 시작해요');
  });

  it('셋째 줄은 제품 원칙이라 선택과 무관하게 고정이다', () => {
    const steps = buildOnboardingNextSteps({
      backfillOptionId: 'all',
      nextRunAt: nextRunFor('6h', '6pm'),
      now: NOW,
    });

    expect(steps).toHaveLength(3);
    expect(steps[2]).toBe(ONBOARDING_APPROVAL_PRINCIPLE_TEXT);
  });
});
