'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFunnel } from '@use-funnel/browser';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';

import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { MotionState, stepReplace, stepReplaceReduced } from '@/shared/motion';
import { automationCredentialsQueries } from '@/shared/queries/automationCredentials.queries';

import { mapOnboardingChannelRows } from '../../api/onboardingSourceMappers';
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
  INITIAL_SCHEDULE_SELECTION,
  ONBOARDING_BACK_LABEL,
  ONBOARDING_BASIC_INFO_TITLE,
  ONBOARDING_COMPLETE_HEADING,
  ONBOARDING_DOC_SETTING_TITLE,
  ONBOARDING_FINISH_LABEL,
  ONBOARDING_NEXT_LABEL,
  ONBOARDING_NEXT_STEPS_TITLE,
  ONBOARDING_PURPOSE_HEADING,
  ONBOARDING_SOURCE_HEADING,
  ONBOARDING_STEPS,
  PURPOSE_FIELD_LABEL,
  SCHEDULE_FIELD_IDS,
  SCHEDULE_FIELDS,
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
import { useWikiOnboardingSubmitMutation } from '../../queries/wikiOnboarding.mutations';
import type { OnboardingChannelListStatus } from '../../types/llmWikiOnboarding';
import { buildOnboardingNextSteps } from '../../utils/onboarding/onboardingNextSteps';
import { buildExecutionAnchor, intervalMinutesOf, resolveNextRunAt } from '../../utils/onboarding/scheduleAnchor';
import { buildScheduleResultSentence } from '../../utils/onboarding/scheduleResultText';
import type { WikiOnboardingDraft, WikiOnboardingSteps } from '../../utils/onboarding/wikiOnboardingSteps';
import { WIKI_ONBOARDING_FUNNEL_ID, WIKI_ONBOARDING_STEP_ORDER } from '../../utils/onboarding/wikiOnboardingSteps';
import { buildOnboardingSummarySections } from './onboardingSummarySections';
import WikiOnboardingCompleteStep from './WikiOnboardingCompleteStep';
import WikiOnboardingPurposeStep from './WikiOnboardingPurposeStep';
import WikiOnboardingSourceStep from './WikiOnboardingSourceStep';

export const EXIT_CONFIRM_TITLE = '온보딩을 그만두시겠어요?';
export const EXIT_CONFIRM_DESCRIPTION = '지금 나가면 작성한 내용이 모두 사라져요.';
export const EXIT_CONFIRM_LABEL = '나가기';

/** 채널 표가 아는 세 상태로 쿼리 상태를 옮긴다 — 빈 목록은 ready + 행 0으로 갈린다 */
const CHANNEL_LIST_STATUS_BY_QUERY: Record<'pending' | 'error' | 'success', OnboardingChannelListStatus> = {
  pending: 'loading',
  error: 'error',
  success: 'ready',
};

/**
 * 온보딩 마법사. 단계는 useFunnel이 소유하고 입력값은 화면이 들고 있는다.
 * 제출은 채널 생성 1회 + 고른 채널톡 채널마다 수집 설정 저장 N회다.
 */
export default function WikiOnboardingPage() {
  const router = useRouter();

  const funnel = useFunnel<WikiOnboardingSteps>({
    id: WIKI_ONBOARDING_FUNNEL_ID,
    initial: { step: 'purpose', context: {} },
  });

  // 새로고침해도 history state에 남은 스냅샷으로 입력을 되살린다
  const restored = funnel.context;

  const prefersReducedMotion = usePrefersReducedMotion();
  // 스텝 교체가 앞으로 가는지 뒤로 오는지. 진행 순서에서의 자리 차이로 읽는다
  const stepIndex = WIKI_ONBOARDING_STEP_ORDER.indexOf(funnel.step);
  const [stepSwap, setStepSwap] = useState({ step: funnel.step, index: stepIndex, direction: 1 });
  if (stepSwap.step !== funnel.step) {
    setStepSwap({ step: funnel.step, index: stepIndex, direction: stepIndex < stepSwap.index ? -1 : 1 });
  }

  const [name, setName] = useState(restored.name ?? '');
  // 선택 필드는 각 목록의 첫 항목으로 시작한다 — 빈 선택으로 여는 화면이 아니다
  const [categoryId, setCategoryId] = useState<string | null>(restored.categoryId ?? WIKI_INFO_CATEGORIES[0].id);
  const [purposeId, setPurposeId] = useState<string | null>(restored.purposeId ?? WIKI_PURPOSE_OPTIONS[0].id);
  const [docKindId, setDocKindId] = useState<string | null>(restored.docKindId ?? WIKI_DOC_KIND_PRESETS[0].id);
  const [toneId, setToneId] = useState<string | null>(restored.toneId ?? WIKI_TONE_STYLE_OPTIONS[0].id);
  // 선택지가 있는 일정 필드만 값이 바뀐다 — 나머지는 픽스처 기본값을 유지한다
  const [scheduleSelection, setScheduleSelection] = useState<Record<string, string>>(
    restored.scheduleSelection ?? INITIAL_SCHEDULE_SELECTION,
  );
  // 표는 고른 채널의 목록이다 — 드롭다운에서 고르면 여기 쌓인다
  const [selectedCredentialIds, setSelectedCredentialIds] = useState<readonly number[]>(
    restored.selectedCredentialIds ?? [],
  );
  const [exitConfirmOpen, setExitConfirmOpen] = useState(false);

  // 소스 후보는 연결된 채널톡 채널이다 — 수집 설정도 이 credential_id로 저장한다
  const credentialsQuery = useQuery(automationCredentialsQueries.credentials('channel_talk'));
  const availableChannelRows = mapOnboardingChannelRows(credentialsQuery.data?.credentials ?? []);
  const channelListStatus: OnboardingChannelListStatus = CHANNEL_LIST_STATUS_BY_QUERY[credentialsQuery.status];

  const submit = useWikiOnboardingSubmitMutation();

  const selectedChannelRows = selectedCredentialIds
    .map((id) => availableChannelRows.find((row) => row.channel.credentialId === id))
    .filter((row) => row !== undefined);

  // 서버 필수값 기준으로 잠근다 — 일정은 기본 선택이 있어 조건에 들지 않는다
  const canLeavePurposeStep = Boolean(name.trim() && categoryId && purposeId && docKindId && toneId);
  const canLeaveSourceStep = selectedCredentialIds.length > 0;

  const scheduleFields = SCHEDULE_FIELDS.map((field) => {
    const picked = field.options?.find((option) => option.id === scheduleSelection[field.id]);
    return picked ? { ...field, valueLabel: picked.label } : field;
  });

  // 초기 기본값에서 하나라도 벗어났으면 나갈 때 잃을 입력이 있다는 뜻이다
  const isDirty =
    name.trim().length > 0 ||
    selectedCredentialIds.length > 0 ||
    categoryId !== WIKI_INFO_CATEGORIES[0].id ||
    purposeId !== WIKI_PURPOSE_OPTIONS[0].id ||
    docKindId !== WIKI_DOC_KIND_PRESETS[0].id ||
    toneId !== WIKI_TONE_STYLE_OPTIONS[0].id ||
    SCHEDULE_FIELDS.some((field) => scheduleSelection[field.id] !== INITIAL_SCHEDULE_SELECTION[field.id]);

  const draftSnapshot = (): WikiOnboardingDraft => ({
    name,
    categoryId,
    purposeId,
    docKindId,
    toneId,
    scheduleSelection,
    selectedCredentialIds,
  });

  // funnel이 스텝마다 history를 쌓아 back은 스텝 후퇴가 된다 — 밖으로 나가는 길은 홈뿐이다
  const exitOnboarding = () => router.push('/');

  const requestExit = () => {
    if (isDirty) setExitConfirmOpen(true);
    else exitOnboarding();
  };

  const submitOnboarding = () => {
    const now = new Date();
    submit.mutate(
      {
        channel: {
          name: name.trim(),
          domain_preset: categoryId ?? '',
          purpose_presets: purposeId ? [purposeId] : [],
          kinds: docKindId ? [docKindId] : [],
          style_preset: toneId ?? '',
        },
        credentialIds: selectedCredentialIds,
        maintenance: {
          enabled: true,
          interval_minutes: intervalMinutesOf(scheduleSelection[SCHEDULE_FIELD_IDS.pollingInterval]),
          execution_anchor_at: buildExecutionAnchor(scheduleSelection[SCHEDULE_FIELD_IDS.runTime], now),
        },
      },
      // 수집 설정이 일부 실패해도 채널은 남는다 — 실패 수만 알리고 대시보드로 보낸다
      { onSuccess: () => router.push('/llm-wiki') },
    );
  };

  return (
    <>
      {/*
       * 스텝 교체는 들어오는 쪽만 움직인다 — funnel.Render는 나가는 사본도 현재 스텝을 그려
       * exit을 걸면 같은 화면이 두 장 겹친다.
       */}
      <motion.div
        key={funnel.step}
        custom={stepSwap.direction}
        variants={prefersReducedMotion ? stepReplaceReduced : stepReplace}
        initial={MotionState.Hidden}
        animate={MotionState.Visible}
      >
        <funnel.Render
          purpose={({ history }) => (
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
              onNext={() => history.push('source', draftSnapshot())}
              nextDisabled={!canLeavePurposeStep}
              onExit={requestExit}
            />
          )}
          source={({ history }) => (
            <WikiOnboardingSourceStep
              steps={ONBOARDING_STEPS}
              heading={ONBOARDING_SOURCE_HEADING}
              channelLabel={CHANNEL_FIELD_LABEL}
              channelCaption={CHANNEL_FIELD_CAPTION}
              channelPickerPlaceholder={CHANNEL_PICKER_PLACEHOLDER}
              channelTableHeaders={CHANNEL_TABLE_HEADERS}
              availableChannels={availableChannelRows}
              onSelectChannel={(credentialId) => setSelectedCredentialIds((current) => [...current, credentialId])}
              channelRows={selectedChannelRows}
              channelListStatus={channelListStatus}
              onRetryChannelList={() => void credentialsQuery.refetch()}
              scheduleFields={scheduleFields}
              onSelectScheduleOption={(fieldId, optionId) =>
                setScheduleSelection((current) => ({ ...current, [fieldId]: optionId }))
              }
              resultText={buildScheduleResultSentence({
                pollingOptionId: scheduleSelection[SCHEDULE_FIELD_IDS.pollingInterval],
                runTimeOptionId: scheduleSelection[SCHEDULE_FIELD_IDS.runTime],
              })}
              backfillNoticeText={BACKFILL_NOTICE_TEXT}
              backLabel={ONBOARDING_BACK_LABEL}
              onBack={() => history.back()}
              nextLabel={ONBOARDING_FINISH_LABEL}
              onNext={() => history.push('complete', draftSnapshot())}
              nextDisabled={!canLeaveSourceStep}
              onExit={requestExit}
            />
          )}
          complete={({ history }) => {
            const now = new Date();
            const intervalMinutes = intervalMinutesOf(scheduleSelection[SCHEDULE_FIELD_IDS.pollingInterval]);
            const nextRunAt = resolveNextRunAt(
              buildExecutionAnchor(scheduleSelection[SCHEDULE_FIELD_IDS.runTime], now),
              intervalMinutes,
              now,
            );

            return (
              <WikiOnboardingCompleteStep
                steps={ONBOARDING_STEPS}
                heading={ONBOARDING_COMPLETE_HEADING}
                summarySections={buildOnboardingSummarySections({
                  name,
                  categoryId,
                  purposeId,
                  docKindId,
                  toneId,
                  scheduleFields,
                  channelRows: selectedChannelRows,
                })}
                nextStepsTitle={ONBOARDING_NEXT_STEPS_TITLE}
                nextSteps={buildOnboardingNextSteps({
                  backfillOptionId: scheduleSelection[SCHEDULE_FIELD_IDS.backfillRange],
                  nextRunAt,
                  now,
                })}
                backLabel={ONBOARDING_BACK_LABEL}
                onBack={() => history.back()}
                finishLabel={ONBOARDING_FINISH_LABEL}
                onFinish={submitOnboarding}
                finishDisabled={submit.isPending || !canLeavePurposeStep || !canLeaveSourceStep}
                onExit={requestExit}
              />
            );
          }}
        />
      </motion.div>

      <ConfirmDialog
        open={exitConfirmOpen}
        onOpenChange={setExitConfirmOpen}
        title={EXIT_CONFIRM_TITLE}
        description={EXIT_CONFIRM_DESCRIPTION}
        confirmLabel={EXIT_CONFIRM_LABEL}
        variant="danger"
        onConfirm={exitOnboarding}
      />
    </>
  );
}
