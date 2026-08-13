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
  DOC_KIND_SAMPLE_TITLE,
  FOLLOW_UP_EXAMPLE,
  FOLLOW_UP_MAX_LENGTH,
  FOLLOW_UP_PLACEHOLDER_TBD,
  ONBOARDING_BASIC_INFO_TITLE,
  ONBOARDING_CHANNEL_ROWS,
  ONBOARDING_FORMAT_TITLE,
  ONBOARDING_NEXT_LABEL,
  ONBOARDING_PURPOSE_HEADING,
  ONBOARDING_SOURCE_HEADING,
  ONBOARDING_STEPS,
  PURPOSE_FIELD_CAPTION,
  PURPOSE_FIELD_LABEL,
  SCHEDULE_FIELDS,
  SCHEDULE_RESULT_TEXT,
  TONE_CUSTOM_MAX_LENGTH,
  TONE_CUSTOM_OPTION,
  TONE_STYLE_FIELD_LABEL,
  WIKI_DOC_KIND_PRESETS,
  WIKI_NAME_FIELD,
  WIKI_PURPOSE_OPTIONS,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import type { OnboardingStepNumber } from '../../utils/onboarding/resolveOnboardingStep';
import WikiOnboardingPurposeStep from './WikiOnboardingPurposeStep';
import WikiOnboardingSourceStep from './WikiOnboardingSourceStep';

interface WikiOnboardingPageProps {
  step: OnboardingStepNumber;
}

/**
 * 온보딩 마법사. 단계는 URL이 소유하고 입력값은 화면이 들고 있는다.
 * 2단계의 진행 버튼과 완료 화면은 시안에 없어 만들지 않는다 — 되돌아가는 길은 브라우저 뒤로가기다.
 */
export default function WikiOnboardingPage({ step }: WikiOnboardingPageProps) {
  const router = useRouter();

  const [name, setName] = useState('');
  const [purposeId, setPurposeId] = useState<string | null>(WIKI_PURPOSE_OPTIONS[0].id);
  const [followUpAnswer, setFollowUpAnswer] = useState('');
  const [docKindId, setDocKindId] = useState<string | null>(WIKI_DOC_KIND_PRESETS[0].id);
  const [toneIds, setToneIds] = useState<readonly string[]>([WIKI_TONE_STYLE_OPTIONS[0].id]);
  const [toneCustom, setToneCustom] = useState('');

  if (step === 2) {
    return (
      <WikiOnboardingSourceStep
        steps={ONBOARDING_STEPS}
        heading={ONBOARDING_SOURCE_HEADING}
        channelLabel={CHANNEL_FIELD_LABEL}
        channelCaption={CHANNEL_FIELD_CAPTION}
        channelPickerPlaceholder={CHANNEL_PICKER_PLACEHOLDER}
        channelTableHeaders={CHANNEL_TABLE_HEADERS}
        channelRows={ONBOARDING_CHANNEL_ROWS}
        scheduleFields={SCHEDULE_FIELDS}
        resultText={SCHEDULE_RESULT_TEXT}
        backfillNoticeText={BACKFILL_NOTICE_TEXT}
      />
    );
  }

  // 예시 문장은 선택한 종류의 것을 보여준다. 선택 연동 여부는 시안에 한 상태뿐이라 미확정이다
  const selectedDocKind = WIKI_DOC_KIND_PRESETS.find((preset) => preset.id === docKindId);

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
        label: PURPOSE_FIELD_LABEL,
        caption: PURPOSE_FIELD_CAPTION,
        options: WIKI_PURPOSE_OPTIONS,
        selectedId: purposeId,
        onSelect: setPurposeId,
        followUpValue: followUpAnswer,
        onFollowUpChange: setFollowUpAnswer,
        followUpPlaceholder: FOLLOW_UP_PLACEHOLDER_TBD,
        followUpMaxLength: FOLLOW_UP_MAX_LENGTH,
        followUpExample: FOLLOW_UP_EXAMPLE,
      }}
      formatTitle={ONBOARDING_FORMAT_TITLE}
      docKind={{
        label: DOC_KIND_FIELD_LABEL,
        presets: WIKI_DOC_KIND_PRESETS,
        selectedId: docKindId,
        onSelect: setDocKindId,
        sampleTitle: DOC_KIND_SAMPLE_TITLE,
        sampleText: selectedDocKind?.sampleText ?? '',
      }}
      tone={{
        label: TONE_STYLE_FIELD_LABEL,
        options: WIKI_TONE_STYLE_OPTIONS,
        selectedIds: toneIds,
        onToggle: (id) =>
          setToneIds((current) => (current.includes(id) ? current.filter((v) => v !== id) : [...current, id])),
        customLabel: TONE_CUSTOM_OPTION.label,
        customDescription: TONE_CUSTOM_OPTION.description,
        customValue: toneCustom,
        onCustomChange: setToneCustom,
        customPlaceholder: FOLLOW_UP_PLACEHOLDER_TBD,
        customMaxLength: TONE_CUSTOM_MAX_LENGTH,
      }}
      nextLabel={ONBOARDING_NEXT_LABEL}
      onNext={() => router.push('/llm-wiki/onboarding?step=2')}
    />
  );
}
