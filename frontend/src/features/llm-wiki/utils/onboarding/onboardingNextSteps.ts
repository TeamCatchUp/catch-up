import { differenceInCalendarDays } from 'date-fns';

import {
  buildOnboardingFirstRunText,
  DEFAULT_BACKFILL_OPTION_ID,
  ONBOARDING_APPROVAL_PRINCIPLE_TEXT,
  ONBOARDING_BACKFILL_START_TEXTS,
} from '../../fixtures/llmWikiOnboardingFixtures';

const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'] as const;

function formatRunDayLabel(nextRunAt: Date, now: Date): string {
  const days = differenceInCalendarDays(nextRunAt, now);
  if (days <= 0) return '오늘';
  if (days === 1) return '내일';
  if (days === 2) return '모레';
  if (days === 7) return `다음 주 ${WEEKDAY_LABELS[nextRunAt.getDay()]}요일`;
  return `${nextRunAt.getMonth() + 1}월 ${nextRunAt.getDate()}일`;
}

/** 주기가 모두 정시 배수라 분은 늘 0이다 — 분이 생기면 여기부터 바꿔야 한다 */
function formatRunHourLabel(nextRunAt: Date): string {
  const hour = nextRunAt.getHours();
  if (hour === 0) return '자정';
  if (hour === 12) return '정오';
  return hour < 12 ? `오전 ${hour}시` : `오후 ${hour - 12}시`;
}

/** 첫 실행 시각을 사람이 읽는 한 마디로. 예: "오늘 오후 6시", "내일 자정" */
export function formatNextRunLabel(nextRunAt: Date, now: Date): string {
  return `${formatRunDayLabel(nextRunAt, now)} ${formatRunHourLabel(nextRunAt)}`;
}

interface NextStepsInput {
  /** 백필 선택. 지금은 "지금부터"만 열려 있고, 열리면 문구가 따라간다 */
  backfillOptionId: string | undefined;
  nextRunAt: Date;
  now: Date;
}

/** 완료 화면 "위키를 만들면" 3줄. ①② 시간 약속은 선택에서 파생되고 ③은 제품 원칙이라 고정이다 */
export function buildOnboardingNextSteps({ backfillOptionId, nextRunAt, now }: NextStepsInput): readonly string[] {
  const backfillText =
    ONBOARDING_BACKFILL_START_TEXTS[backfillOptionId ?? ''] ??
    ONBOARDING_BACKFILL_START_TEXTS[DEFAULT_BACKFILL_OPTION_ID];

  return [
    backfillText,
    buildOnboardingFirstRunText(formatNextRunLabel(nextRunAt, now)),
    ONBOARDING_APPROVAL_PRINCIPLE_TEXT,
  ];
}
