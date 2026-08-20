import {
  CHANNEL_TABLE_HEADERS,
  ONBOARDING_SUMMARY_CHANNEL_LABEL,
  ONBOARDING_SUMMARY_SECTIONS,
  SCHEDULE_FIELD_IDS,
  WIKI_DOC_KIND_PRESETS,
  WIKI_INFO_CATEGORIES,
  WIKI_PURPOSE_OPTIONS,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import type { OnboardingChannelRow, ScheduleFieldData } from '../../types/llmWikiOnboarding';
import OnboardingChannelTable from './OnboardingChannelTable';
import type { SummarySectionView } from './OnboardingSummaryCard';

export interface OnboardingSummaryInput {
  name: string;
  categoryId: string | null;
  purposeId: string | null;
  docKindId: string | null;
  toneId: string | null;
  /** 트리거에 보이는 값이 그대로 요약이 된다 — 두 화면이 어긋나면 고르지 않은 설정을 본 셈이다 */
  scheduleFields: readonly ScheduleFieldData[];
  channelRows: readonly OnboardingChannelRow[];
}

/** 값이 없는 행은 undefined로 남겨 픽스처 값을 그대로 쓰게 한다 */
const summaryValues = (label: string | undefined) => (label ? [label] : undefined);

/** 요약 두 구역을 모두 실제 선택으로 채운다. 픽스처 값은 행 순서와 라벨만 공급한다 */
export function buildOnboardingSummarySections(input: OnboardingSummaryInput): readonly SummarySectionView[] {
  const category = WIKI_INFO_CATEGORIES.find((item) => item.id === input.categoryId);
  const purpose = WIKI_PURPOSE_OPTIONS.find((item) => item.id === input.purposeId);
  const docKind = WIKI_DOC_KIND_PRESETS.find((item) => item.id === input.docKindId);
  const tone = WIKI_TONE_STYLE_OPTIONS.find((item) => item.id === input.toneId);
  const scheduleValueOf = (fieldId: string) => input.scheduleFields.find((field) => field.id === fieldId)?.valueLabel;

  const [purposeSection, collectionSection] = ONBOARDING_SUMMARY_SECTIONS;
  const overrides: Record<string, readonly string[] | undefined> = {
    이름: input.name ? [input.name] : [],
    '정리할 정보': category ? [category.label] : [],
    목적: purpose ? [purpose.label] : [],
    '문서 종류': docKind ? [docKind.label] : [],
    문체: tone ? [tone.label] : [],
    '갱신 주기': summaryValues(scheduleValueOf(SCHEDULE_FIELD_IDS.pollingInterval)),
    언제부터: summaryValues(scheduleValueOf(SCHEDULE_FIELD_IDS.backfillRange)),
    실행시간: summaryValues(scheduleValueOf(SCHEDULE_FIELD_IDS.runTime)),
  };

  const fillRows = (section: (typeof ONBOARDING_SUMMARY_SECTIONS)[number]) =>
    section.rows.map((row) => ({ ...row, values: overrides[row.label] ?? row.values }));

  return [
    { ...purposeSection, rows: fillRows(purposeSection) },
    {
      ...collectionSection,
      rows: fillRows(collectionSection),
      // 채널은 행이 아니라 2단계와 같은 표로 놓인다
      lead: {
        label: ONBOARDING_SUMMARY_CHANNEL_LABEL,
        content: <OnboardingChannelTable headers={CHANNEL_TABLE_HEADERS} rows={input.channelRows} />,
      },
    },
  ];
}
