'use client';

import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconCalendarClock from '@/public/icons/icon/calendar_clock.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconClock from '@/public/icons/icon/clock.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';
import IconTagChannel from '@/public/icons/icon/tag_channel.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

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
import OnboardingTopBar from './OnboardingTopBar';

interface ScheduleTriggerFieldProps {
  field: ScheduleFieldData;
  onSelectOption?: (fieldId: string, optionId: string) => void;
  onOpenRequest?: (id: string) => void;
}

/** 일정 필드. 선택지가 있으면 드롭다운으로 열고, 없으면 트리거만 그린다 */
function ScheduleTriggerField({ field, onSelectOption, onOpenRequest }: ScheduleTriggerFieldProps) {
  const TriggerIcon = field.icon === 'calendar-clock' ? IconCalendarClock : IconClock;
  const trigger = (
    <button
      type="button"
      onClick={field.options ? undefined : () => onOpenRequest?.(field.id)}
      className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover data-[state=open]:bg-fill-normal-interaction-pressed flex h-11.5 w-full cursor-pointer items-center gap-2 rounded-xl border px-3 transition-colors"
    >
      <TriggerIcon className="text-icon-normal-normal size-5.5 shrink-0" />
      <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate text-left">
        {field.valueLabel}
      </span>
      <IconArrowDown className="text-icon-normal-normal size-6 shrink-0" />
    </button>
  );

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <OnboardingFieldLabel label={field.label} required size="body" />
      {field.options ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            sideOffset={2}
            className="bg-fill-normal-normal flex w-[var(--radix-dropdown-menu-trigger-width)] min-w-0 flex-col gap-1 rounded-xl px-1.5 py-2"
          >
            {field.options.map((option) => (
              <DropdownMenuItem
                key={option.id}
                disabled={option.disabled}
                onSelect={() => onSelectOption?.(field.id, option.id)}
                className={cn(
                  'text-body-small text-text-normal-normal h-8 px-2',
                  option.label === field.valueLabel && 'bg-fill-normal-interaction-hover',
                )}
              >
                <span className="flex-1 truncate">{option.label}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        trigger
      )}
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
  /** 드롭다운에 뜨는 선택 가능한 채널. 이미 고른 채널은 목록에서 빠진다 */
  availableChannels?: readonly OnboardingChannelRow[];
  onSelectChannel?: (credentialId: number) => void;
  onOpenChannelPicker?: () => void;
  channelTableHeaders: { name: string; lastModified: string };
  /** 표는 고른 채널의 목록이다 */
  channelRows: readonly OnboardingChannelRow[];
  channelListStatus?: OnboardingChannelListStatus;
  onRetryChannelList?: () => void;
  scheduleFields: readonly ScheduleFieldData[];
  onSelectScheduleOption?: (fieldId: string, optionId: string) => void;
  onOpenScheduleField?: (id: string) => void;
  /** 실행 시각 아래 결과 문장 — 값 조합별 변형 규칙은 미확정이라 문자열로 받는다 */
  resultText: string;
  backfillNoticeText: string;
  backLabel: string;
  onBack?: () => void;
  nextLabel: string;
  onNext?: () => void;
  /** 소스 채널을 하나도 고르지 않으면 잠긴다 — 수집 설정은 채널마다 저장된다 */
  nextDisabled?: boolean;
  /** 상단 바 뒤로가기 — 하단 "이전"(단계 후퇴)과 달리 온보딩을 벗어난다 */
  onExit?: () => void;
}

// 온보딩 2단계 화면 조립. 8/14 시안에서 일정이 3열로 바뀌고 하단 액션 바가 신설됐다
export default function WikiOnboardingSourceStep({
  steps,
  heading,
  channelLabel,
  channelCaption,
  channelPickerPlaceholder,
  availableChannels,
  onSelectChannel,
  onOpenChannelPicker,
  channelTableHeaders,
  channelRows,
  channelListStatus,
  onRetryChannelList,
  scheduleFields,
  onSelectScheduleOption,
  onOpenScheduleField,
  resultText,
  backfillNoticeText,
  backLabel,
  onBack,
  nextLabel,
  onNext,
  nextDisabled,
  onExit,
}: WikiOnboardingSourceStepProps) {
  // 이미 고른 채널은 다시 고를 수 없다 — 표에 같은 채널이 두 번 들어가지 않게 한다
  const selectedIds = new Set(channelRows.map((row) => row.channel.credentialId));
  const selectableChannels = (availableChannels ?? []).filter((row) => !selectedIds.has(row.channel.credentialId));

  const channelPickerTrigger = (
    <button
      type="button"
      onClick={availableChannels ? undefined : onOpenChannelPicker}
      className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover data-[state=open]:bg-fill-normal-interaction-pressed flex h-11.5 w-full cursor-pointer items-center gap-1.5 rounded-lg border px-3 transition-colors"
    >
      <span className="bg-fill-normal-strong flex shrink-0 items-center justify-center rounded-lg p-1">
        <IconAddSmall className="text-icon-primary-normal size-5.5" />
      </span>
      <span className="text-body-small text-text-normal-assistive min-w-0 flex-1 truncate text-left">
        {channelPickerPlaceholder}
      </span>
      <IconArrowDown className="text-icon-normal-normal size-6 shrink-0" />
    </button>
  );

  return (
    <div className="bg-fill-normal-assistive flex w-full flex-col">
      <OnboardingTopBar onBack={onExit} />
      <div className="flex flex-col gap-8 px-16 pt-5 pb-9">
        <OnboardingStepper steps={steps} currentStep={2} />
        <h1 className="text-heading-xlarge text-text-normal-normal">{heading}</h1>

        <div className="bg-fill-normal-normal border-line-normal-neutral flex flex-col gap-8 rounded-2xl border p-8">
          <div className="flex flex-col gap-3">
            <OnboardingFieldLabel label={channelLabel} required />
            <p className="text-body-small text-text-normal-alternative">{channelCaption}</p>
            {availableChannels ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>{channelPickerTrigger}</DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  sideOffset={2}
                  className="bg-fill-normal-normal flex max-h-80 w-[var(--radix-dropdown-menu-trigger-width)] min-w-0 flex-col gap-1 overflow-y-auto rounded-xl px-1.5 py-2"
                >
                  {selectableChannels.map((row) => (
                    <DropdownMenuItem
                      key={row.channel.credentialId}
                      onSelect={() => onSelectChannel?.(row.channel.credentialId)}
                      className="text-body-small text-text-normal-normal h-8 gap-3 px-2"
                    >
                      <IconTagChannel className="text-icon-normal-neutral size-5 shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{row.channel.name}</span>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              channelPickerTrigger
            )}
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
                <ScheduleTriggerField
                  key={field.id}
                  field={field}
                  onSelectOption={onSelectScheduleOption}
                  onOpenRequest={onOpenScheduleField}
                />
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

      <OnboardingActionBar
        backLabel={backLabel}
        onBack={onBack}
        nextLabel={nextLabel}
        onNext={onNext}
        nextDisabled={nextDisabled}
      />
    </div>
  );
}
