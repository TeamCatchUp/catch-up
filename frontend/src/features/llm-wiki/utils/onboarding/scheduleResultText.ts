import { buildScheduleResultText, SCHEDULE_FIELD_IDS, SCHEDULE_FIELDS } from '../../fixtures/llmWikiOnboardingFixtures';

/** 고른 선택지의 라벨. 미지 선택은 트리거에 그려진 기본값으로 떨어진다 */
function optionLabelOf(fieldId: string, optionId: string | undefined): string {
  const field = SCHEDULE_FIELDS.find((item) => item.id === fieldId);
  return field?.options?.find((option) => option.id === optionId)?.label ?? field?.valueLabel ?? '';
}

interface ScheduleResultInput {
  pollingOptionId: string | undefined;
  runTimeOptionId: string | undefined;
}

/** 2단계 하단 결과 문장. 3단계 요약과 같은 선택에서 파생돼 두 화면이 어긋나지 않는다 */
export function buildScheduleResultSentence({ pollingOptionId, runTimeOptionId }: ScheduleResultInput): string {
  return buildScheduleResultText(
    optionLabelOf(SCHEDULE_FIELD_IDS.pollingInterval, pollingOptionId),
    optionLabelOf(SCHEDULE_FIELD_IDS.runTime, runTimeOptionId),
  );
}
