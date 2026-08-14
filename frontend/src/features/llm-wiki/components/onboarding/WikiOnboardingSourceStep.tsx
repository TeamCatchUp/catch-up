'use client';

import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconClock from '@/public/icons/icon/clock.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';

import type {
  OnboardingChannelListStatus,
  OnboardingChannelRow,
  OnboardingStepInfo,
  ScheduleFieldData,
} from '../../types/llmWikiOnboarding';
import OnboardingActionBar from './OnboardingActionBar';
import OnboardingChannelTable from './OnboardingChannelTable';
import OnboardingFieldLabel from './OnboardingFieldLabel';
import OnboardingStepper from './OnboardingStepper';

interface ScheduleTriggerFieldProps {
  field: ScheduleFieldData;
  onOpenRequest?: (id: string) => void;
}

// 닫힌 드롭다운 트리거만 그린다 — 열림 메뉴·옵션 목록은 시안에 없다
function ScheduleTriggerField({ field, onOpenRequest }: ScheduleTriggerFieldProps) {
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <OnboardingFieldLabel label={field.label} required size="body" />
      <button
        type="button"
        onClick={() => onOpenRequest?.(field.id)}
        className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover flex h-11.5 w-full cursor-pointer items-center gap-2 rounded-xl border px-3 transition-colors"
      >
        <IconClock className="text-icon-normal-normal size-5.5 shrink-0" />
        <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate text-left">
          {field.valueLabel}
        </span>
        <IconArrowDown className="text-icon-normal-normal size-6 shrink-0" />
      </button>
    </div>
  );
}

interface WikiOnboardingSourceStepProps {
  steps: readonly OnboardingStepInfo[];
  heading: string;
  channelLabel: string;
  /** 수집 범위 오해 방지 카피 */
  channelCaption: string;
  channelPickerPlaceholder: string;
  onOpenChannelPicker?: () => void;
  channelTableHeaders: { name: string; lastModified: string };
  channelRows: readonly OnboardingChannelRow[];
  channelListStatus?: OnboardingChannelListStatus;
  onRetryChannelList?: () => void;
  scheduleFields: readonly ScheduleFieldData[];
  onOpenScheduleField?: (id: string) => void;
  /** 실행 시각 아래 결과 문장 — 값 조합별 변형 규칙은 미확정이라 문자열로 받는다 */
  resultText: string;
  backfillNoticeText: string;
  backLabel: string;
  onBack?: () => void;
  nextLabel: string;
  onNext?: () => void;
}

// 온보딩 2단계 화면 조립. 8/14 시안에서 일정이 3열로 바뀌고 하단 액션 바가 신설됐다
export default function WikiOnboardingSourceStep({
  steps,
  heading,
  channelLabel,
  channelCaption,
  channelPickerPlaceholder,
  onOpenChannelPicker,
  channelTableHeaders,
  channelRows,
  channelListStatus,
  onRetryChannelList,
  scheduleFields,
  onOpenScheduleField,
  resultText,
  backfillNoticeText,
  backLabel,
  onBack,
  nextLabel,
  onNext,
}: WikiOnboardingSourceStepProps) {
  return (
    <div className="flex w-full flex-col">
      <div className="flex flex-col gap-8 px-16 pt-5 pb-9">
        <OnboardingStepper steps={steps} currentStep={2} />
        <h1 className="text-heading-xlarge text-text-normal-normal">{heading}</h1>

        <div className="bg-fill-normal-normal border-line-normal-neutral flex flex-col gap-8 rounded-2xl border p-8">
          <div className="flex flex-col gap-3">
            <OnboardingFieldLabel label={channelLabel} required />
            <p className="text-body-small text-text-normal-alternative">{channelCaption}</p>
            <button
              type="button"
              onClick={onOpenChannelPicker}
              className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover flex h-11.5 w-full cursor-pointer items-center gap-2 rounded-xl border px-3 transition-colors"
            >
              <span className="bg-fill-normal-strong flex size-7.5 shrink-0 items-center justify-center rounded-full">
                <IconAddSmall className="text-icon-normal-normal size-5.5" />
              </span>
              <span className="text-body-small text-text-normal-assistive min-w-0 flex-1 truncate text-left">
                {channelPickerPlaceholder}
              </span>
              <IconArrowDown className="text-icon-normal-normal size-6 shrink-0" />
            </button>
            <OnboardingChannelTable
              headers={channelTableHeaders}
              rows={channelRows}
              status={channelListStatus}
              onRetry={onRetryChannelList}
            />
          </div>

          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-3 gap-4">
              {scheduleFields.map((field) => (
                <ScheduleTriggerField key={field.id} field={field} onOpenRequest={onOpenScheduleField} />
              ))}
            </div>
            <div className="flex items-center gap-1">
              <IconCheck className="text-icon-primary-assistive size-5.5 shrink-0" />
              <span className="text-label-xsmall text-text-primary-assistive">{resultText}</span>
            </div>
          </div>

          <div className="bg-fill-primary-normal-neutral flex items-center gap-2 rounded-lg px-2 py-1.5">
            <IconMegaphone className="text-icon-primary-assistive size-4.5 shrink-0" />
            <span className="text-label-xsmall text-text-primary-assistive">{backfillNoticeText}</span>
          </div>
        </div>
      </div>

      <OnboardingActionBar backLabel={backLabel} onBack={onBack} nextLabel={nextLabel} onNext={onNext} />
    </div>
  );
}
