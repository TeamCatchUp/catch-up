'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  BACKFILL_NOTICE_TEXT,
  CHANNEL_FIELD_CAPTION,
  CHANNEL_FIELD_LABEL,
  CHANNEL_PICKER_PLACEHOLDER,
  CHANNEL_TABLE_HEADERS,
  DOC_KIND_FIELD_LABEL,
  DOC_KIND_SAMPLE_CAPTION,
  DOC_KIND_SAMPLE_TITLE,
  INFO_CATEGORY_FIELD_LABEL,
  ONBOARDING_BACK_LABEL,
  ONBOARDING_BASIC_INFO_TITLE,
  ONBOARDING_CHANNEL_ROWS,
  ONBOARDING_COMPLETE_HEADING,
  ONBOARDING_DOC_SETTING_TITLE,
  ONBOARDING_FINISH_LABEL,
  ONBOARDING_NEXT_LABEL,
  ONBOARDING_NEXT_STEPS,
  ONBOARDING_NEXT_STEPS_TITLE,
  ONBOARDING_PURPOSE_HEADING,
  ONBOARDING_SOURCE_HEADING,
  ONBOARDING_STEPS,
  ONBOARDING_SUMMARY_CHANNEL_LABEL,
  ONBOARDING_SUMMARY_SECTIONS,
  PURPOSE_FIELD_LABEL,
  SCHEDULE_FIELDS,
  SCHEDULE_RESULT_TEXT,
  TEMPLATE_SAMPLE_TEXT_TBD,
  TONE_SAMPLE_TAG_LABEL,
  TONE_STYLE_FIELD_LABEL,
  WIKI_DOC_KIND_PRESETS,
  WIKI_INFO_CATEGORIES,
  WIKI_NAME_FIELD,
  WIKI_PURPOSE_OPTIONS,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import { WIKI_DOC_TEMPLATE_SAMPLES } from '../../fixtures/llmWikiTemplateSamples';
import type { OnboardingChannelRow } from '../../types/llmWikiOnboarding';
import type { OnboardingStepNumber } from '../../utils/onboarding/resolveOnboardingStep';
import OnboardingChannelTable from './OnboardingChannelTable';
import type { SummarySectionView } from './OnboardingSummaryCard';
import WikiOnboardingCompleteStep from './WikiOnboardingCompleteStep';
import WikiOnboardingPurposeStep from './WikiOnboardingPurposeStep';
import WikiOnboardingSourceStep from './WikiOnboardingSourceStep';

interface WikiOnboardingPageProps {
  step: OnboardingStepNumber;
}

const ONBOARDING_PATH = '/llm-wiki/onboarding';

/**
 * 온보딩 마법사. 단계는 URL이 소유하고 입력값은 화면이 들고 있는다.
 * 완료 후 이동만 하고 위키를 만들지는 않는다 — 생성 API가 아직 없다.
 */
export default function WikiOnboardingPage({ step }: WikiOnboardingPageProps) {
  const router = useRouter();

  const [name, setName] = useState('');
  const [categoryId, setCategoryId] = useState<string | null>(WIKI_INFO_CATEGORIES[0].id);
  const [purposeId, setPurposeId] = useState<string | null>(WIKI_PURPOSE_OPTIONS[0].id);
  const [docKindId, setDocKindId] = useState<string | null>(WIKI_DOC_KIND_PRESETS[0].id);
  const [toneId, setToneId] = useState<string | null>(WIKI_TONE_STYLE_OPTIONS[0].id);
  // 선택지가 있는 일정 필드만 값이 바뀐다 — 나머지는 픽스처 기본값을 유지한다
  const [scheduleSelection, setScheduleSelection] = useState<Record<string, string>>({});
  // 표는 고른 채널의 목록이다 — 드롭다운에서 고르면 여기 쌓인다
  const [selectedCredentialIds, setSelectedCredentialIds] = useState<readonly number[]>([]);

  const selectedChannelRows = selectedCredentialIds
    .map((id) => ONBOARDING_CHANNEL_ROWS.find((row) => row.channel.credentialId === id))
    .filter((row) => row !== undefined);

  const scheduleFields = SCHEDULE_FIELDS.map((field) => {
    const picked = field.options?.find((option) => option.id === scheduleSelection[field.id]);
    return picked ? { ...field, valueLabel: picked.label } : field;
  });

  const goToStep = (next: OnboardingStepNumber) =>
    router.push(next === 1 ? ONBOARDING_PATH : `${ONBOARDING_PATH}?step=${next}`);

  if (step === 3) {
    return (
      <WikiOnboardingCompleteStep
        steps={ONBOARDING_STEPS}
        heading={ONBOARDING_COMPLETE_HEADING}
        summarySections={buildSummarySections({
          name,
          categoryId,
          purposeId,
          docKindId,
          toneId,
          channelRows: selectedChannelRows,
        })}
        nextStepsTitle={ONBOARDING_NEXT_STEPS_TITLE}
        nextSteps={ONBOARDING_NEXT_STEPS}
        backLabel={ONBOARDING_BACK_LABEL}
        onBack={() => goToStep(2)}
        finishLabel={ONBOARDING_FINISH_LABEL}
        onFinish={() => router.push('/llm-wiki')}
        onExit={() => router.back()}
      />
    );
  }

  if (step === 2) {
    return (
      <WikiOnboardingSourceStep
        steps={ONBOARDING_STEPS}
        heading={ONBOARDING_SOURCE_HEADING}
        channelLabel={CHANNEL_FIELD_LABEL}
        channelCaption={CHANNEL_FIELD_CAPTION}
        channelPickerPlaceholder={CHANNEL_PICKER_PLACEHOLDER}
        channelTableHeaders={CHANNEL_TABLE_HEADERS}
        availableChannels={ONBOARDING_CHANNEL_ROWS}
        onSelectChannel={(credentialId) => setSelectedCredentialIds((current) => [...current, credentialId])}
        channelRows={selectedChannelRows}
        scheduleFields={scheduleFields}
        onSelectScheduleOption={(fieldId, optionId) =>
          setScheduleSelection((current) => ({ ...current, [fieldId]: optionId }))
        }
        resultText={SCHEDULE_RESULT_TEXT}
        backfillNoticeText={BACKFILL_NOTICE_TEXT}
        backLabel={ONBOARDING_BACK_LABEL}
        onBack={() => goToStep(1)}
        nextLabel={ONBOARDING_FINISH_LABEL}
        onNext={() => goToStep(3)}
        onExit={() => router.back()}
      />
    );
  }

  return (
    <WikiOnboardingPurposeStep
      steps={ONBOARDING_STEPS}
      heading={ONBOARDING_PURPOSE_HEADING}
      basicInfoTitle={ONBOARDING_BASIC_INFO_TITLE}
      nameLabel={WIKI_NAME_FIELD.label}
      nameValue={name}
      onNameChange={setName}
      namePlaceholder={WIKI_NAME_FIELD.placeholder}
      nameMaxLength={WIKI_NAME_FIELD.maxLength}
      purpose={{
        categoryLabel: INFO_CATEGORY_FIELD_LABEL,
        categories: WIKI_INFO_CATEGORIES,
        selectedCategoryId: categoryId,
        onSelectCategory: setCategoryId,
        purposeLabel: PURPOSE_FIELD_LABEL,
        purposeOptions: WIKI_PURPOSE_OPTIONS,
        selectedPurposeId: purposeId,
        onSelectPurpose: setPurposeId,
      }}
      docSettingTitle={ONBOARDING_DOC_SETTING_TITLE}
      docKind={{
        label: DOC_KIND_FIELD_LABEL,
        presets: WIKI_DOC_KIND_PRESETS,
        selectedId: docKindId,
        onSelect: setDocKindId,
        sampleTitle: DOC_KIND_SAMPLE_TITLE,
        sampleCaption: DOC_KIND_SAMPLE_CAPTION,
        // 양식이 없는 종류는 아직 없지만, 종류가 열린 타입이라 필러를 폴백으로 둔다
        sampleText: WIKI_DOC_TEMPLATE_SAMPLES[docKindId ?? ''] ?? TEMPLATE_SAMPLE_TEXT_TBD,
      }}
      tone={{
        label: TONE_STYLE_FIELD_LABEL,
        options: WIKI_TONE_STYLE_OPTIONS,
        selectedId: toneId,
        onSelect: setToneId,
        sampleTagLabel: TONE_SAMPLE_TAG_LABEL,
      }}
      nextLabel={ONBOARDING_NEXT_LABEL}
      onNext={() => goToStep(2)}
      onExit={() => router.back()}
    />
  );
}

interface SummaryInput {
  name: string;
  categoryId: string | null;
  purposeId: string | null;
  docKindId: string | null;
  toneId: string | null;
  channelRows: readonly OnboardingChannelRow[];
}

/** 1단계 선택분만 실제 입력으로 채운다 — 2단계는 선택 UI가 시안에 없어 픽스처 값을 유지한다 */
function buildSummarySections(input: SummaryInput): readonly SummarySectionView[] {
  const category = WIKI_INFO_CATEGORIES.find((item) => item.id === input.categoryId);
  const purpose = WIKI_PURPOSE_OPTIONS.find((item) => item.id === input.purposeId);
  const docKind = WIKI_DOC_KIND_PRESETS.find((item) => item.id === input.docKindId);
  const tone = WIKI_TONE_STYLE_OPTIONS.find((item) => item.id === input.toneId);

  const [purposeSection, collectionSection] = ONBOARDING_SUMMARY_SECTIONS;
  const overrides: Record<string, readonly string[]> = {
    이름: input.name ? [input.name] : [],
    '정리할 정보': category ? [category.label] : [],
    목적: purpose ? [purpose.label] : [],
    '문서 종류': docKind ? [docKind.label] : [],
    문체: tone ? [tone.label] : [],
  };

  return [
    {
      ...purposeSection,
      rows: purposeSection.rows.map((row) => ({ ...row, values: overrides[row.label] ?? row.values })),
    },
    {
      ...collectionSection,
      // 채널은 행이 아니라 2단계와 같은 표로 놓인다
      lead: {
        label: ONBOARDING_SUMMARY_CHANNEL_LABEL,
        content: <OnboardingChannelTable headers={CHANNEL_TABLE_HEADERS} rows={input.channelRows} />,
      },
    },
  ];
}
