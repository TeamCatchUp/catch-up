import { describe, expect, it } from 'vitest';

import { INITIAL_SCHEDULE_SELECTION, SCHEDULE_FIELD_IDS } from '../../fixtures/llmWikiOnboardingFixtures';
import { buildScheduleResultSentence } from './scheduleResultText';

const INITIAL_INPUT = {
  pollingOptionId: INITIAL_SCHEDULE_SELECTION[SCHEDULE_FIELD_IDS.pollingInterval],
  runTimeOptionId: INITIAL_SCHEDULE_SELECTION[SCHEDULE_FIELD_IDS.runTime],
};

describe('buildScheduleResultSentence', () => {
  it('기본 선택은 트리거 기본값(매일·자정)을 그대로 말한다', () => {
    expect(buildScheduleResultSentence(INITIAL_INPUT)).toBe('매일 자정에 새 상담을 확인하고 문서 초안을 만들어요.');
  });

  it('주기를 바꾸면 문장이 따라간다', () => {
    expect(buildScheduleResultSentence({ ...INITIAL_INPUT, pollingOptionId: '6h' })).toBe(
      '6시간마다 자정에 새 상담을 확인하고 문서 초안을 만들어요.',
    );
  });

  it('실행 시각을 바꾸면 문장이 따라간다', () => {
    expect(buildScheduleResultSentence({ ...INITIAL_INPUT, runTimeOptionId: '6pm' })).toBe(
      '매일 오후 6시에 새 상담을 확인하고 문서 초안을 만들어요.',
    );
  });

  it('둘 다 바꾸면 둘 다 반영된다', () => {
    expect(buildScheduleResultSentence({ pollingOptionId: 'weekly', runTimeOptionId: 'noon' })).toBe(
      '주 1회 정오에 새 상담을 확인하고 문서 초안을 만들어요.',
    );
  });

  it('모르는 선택은 트리거 기본값으로 떨어진다', () => {
    expect(buildScheduleResultSentence({ pollingOptionId: undefined, runTimeOptionId: 'nope' })).toBe(
      '매일 자정에 새 상담을 확인하고 문서 초안을 만들어요.',
    );
  });
});
